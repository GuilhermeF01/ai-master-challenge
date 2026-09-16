# Lead Scorer — solução completa

Entrego uma ferramenta em **Streamlit** (com versão CLI para quem não quer abrir browser), scoring baseado em **taxas históricas + heurística de timing**, totalmente explicável linha a linha, filtros por escritório/manager/vendedor, um backtest para validar a "chance de fechar" e testes unitários.

Observação importante: nesta sessão não tenho acesso a arquivos nem execução, então o código foi revisado por leitura, não executado. No fim listo o que conferir ao rodar pela primeira vez.

## Estrutura

```
lead-scorer/
├── app.py              # UI do vendedor (Streamlit)
├── scoring.py          # toda a lógica de scoring (sem UI)
├── cli.py              # mesma coisa no terminal
├── backtest.py         # valida a "chance de fechar" fora da amostra
├── test_scoring.py     # pytest
├── requirements.txt
├── README.md           # setup, lógica, limitações
├── PROCESS_LOG.md      # como a IA foi usada
└── data/               # os 4 CSVs do Kaggle (não versionados)
```

---

## `scoring.py`

```python
"""
Lead Scorer — lógica de scoring do pipeline (sem UI).

Pergunta que o score responde: "quanto vale o meu tempo neste deal, hoje?"

    Chance de fechar = histórico Won/Lost por produto, conta e vendedor (com shrinkage),
                       combinado em log-odds
    Ticket típico    = mediana do close_value dos deals ganhos daquele produto
    Timing           = fator heurístico: dias aberto vs. ciclo de venda típico do produto
    Prioridade       = Chance × Ticket × Timing
    Score (0–100)    = percentil da Prioridade entre todos os deals abertos

O que é aprendido dos dados fica em `History`; o que é regra de negócio ajustável fica
em `ScoringConfig`. Rode `python scoring.py` para gerar `scored_pipeline.csv`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
OPEN_STAGES = ("Prospecting", "Engaging")
CLOSED_STAGES = ("Won", "Lost")
FACTORS = ("product", "account", "sales_agent")
PRODUCT_FIXES = {"GTXPro": "GTX Pro"}  # typo conhecido em sales_pipeline.csv vs products.csv
TIMING_ORDER = ["Janela de fechamento", "No prazo", "Atrasando", "Esfriando", "Qualificar"]


# --------------------------------------------------------------------------- config
@dataclass
class ScoringConfig:
    """Parâmetros de negócio. RevOps ajusta aqui (ou pelos sliders do app)."""

    shrinkage_k: float = 20.0  # grupos com poucos deals são puxados para a taxa global
    w_product: float = 1.0
    w_account: float = 1.0
    w_agent: float = 0.5  # peso menor: o histórico do vendedor informa, mas não domina
    timing_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "Qualificar": 0.8,  # Prospecting: ainda não há engajamento real
            "No prazo": 1.0,  # abaixo do p25 do ciclo dos deals ganhos
            "Janela de fechamento": 1.2,  # entre p25 e p75: é quando a maioria fecha
            "Atrasando": 0.9,  # entre p75 e p90
            "Esfriando": 0.6,  # acima do p90: resgatar ou encerrar
        }
    )

    @property
    def weights(self) -> dict[str, float]:
        return {"product": self.w_product, "account": self.w_account, "sales_agent": self.w_agent}


@dataclass
class History:
    """Tudo que foi aprendido dos deals fechados."""

    base_rate: float
    rates: dict[str, pd.DataFrame]  # por fator: wins, n, rate (suavizada)
    ticket_by_product: pd.Series
    global_ticket: float
    cycle_q: pd.DataFrame  # por produto: q25, q75, q90 (dias) dos deals ganhos
    global_cycle_q: dict[str, float]


@dataclass
class ScoringResult:
    deals: pd.DataFrame  # deals abertos, scorados e ordenados
    history: History
    cfg: ScoringConfig
    ref_date: pd.Timestamp
    high_value: float  # mediana do valor esperado: separa "vale resgatar" de "pode encerrar"


# --------------------------------------------------------------------------- dados
def load_data(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Lê os 4 CSVs e devolve o pipeline com vendedor, produto e conta já juntados."""
    accounts = pd.read_csv(data_dir / "accounts.csv")
    products = pd.read_csv(data_dir / "products.csv")
    teams = pd.read_csv(data_dir / "sales_teams.csv")
    pipeline = pd.read_csv(data_dir / "sales_pipeline.csv")

    for df in (accounts, products, teams, pipeline):
        for col in df.columns:
            is_text = pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])
            if is_text and df[col].notna().any():
                df[col] = df[col].str.strip()

    pipeline["product"] = pipeline["product"].replace(PRODUCT_FIXES)
    pipeline["engage_date"] = pd.to_datetime(pipeline["engage_date"], errors="coerce")
    pipeline["close_date"] = pd.to_datetime(pipeline["close_date"], errors="coerce")
    pipeline["close_value"] = pd.to_numeric(pipeline["close_value"], errors="coerce")

    acc_cols = [c for c in ("account", "sector", "revenue", "employees") if c in accounts.columns]
    return (
        pipeline.merge(teams, on="sales_agent", how="left")
        .merge(products, on="product", how="left")
        .merge(accounts[acc_cols], on="account", how="left")
    )


# --------------------------------------------------------------------------- aprendizado
def smoothed_win_rate(closed: pd.DataFrame, key: str, base_rate: float, k: float) -> pd.DataFrame:
    """Taxa de conversão por grupo com shrinkage: (wins + k·base) / (n + k).

    Um grupo com 2 deals e 2 wins não vira "100%": com k=20 ele fica perto da média global.
    """
    g = closed.groupby(key)["won"].agg(wins="sum", n="count")
    g["rate"] = (g["wins"] + k * base_rate) / (g["n"] + k)
    return g


def fit_history(closed: pd.DataFrame, cfg: ScoringConfig) -> History:
    closed = closed.copy()
    if closed.empty:
        raise ValueError("Sem deals fechados (Won/Lost) para aprender o histórico.")
    closed["won"] = (closed["deal_stage"] == "Won").astype(int)
    base_rate = float(closed["won"].mean())
    rates = {f: smoothed_win_rate(closed, f, base_rate, cfg.shrinkage_k) for f in FACTORS}

    won = closed[closed["won"] == 1].copy()
    won["cycle_days"] = (won["close_date"] - won["engage_date"]).dt.days
    qs = [0.25, 0.75, 0.90]
    cycle_q = won.groupby("product")["cycle_days"].quantile(qs).unstack()
    cycle_q.columns = ["q25", "q75", "q90"]
    global_q = dict(zip(["q25", "q75", "q90"], won["cycle_days"].quantile(qs).tolist()))

    return History(
        base_rate=base_rate,
        rates=rates,
        ticket_by_product=won.groupby("product")["close_value"].median(),
        global_ticket=float(won["close_value"].median()),
        cycle_q=cycle_q,
        global_cycle_q=global_q,
    )


# --------------------------------------------------------------------------- scoring
def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + np.exp(-np.asarray(x, dtype=float)))


def add_win_probability(deals: pd.DataFrame, hist: History, cfg: ScoringConfig) -> pd.DataFrame:
    """Combina as taxas por fator em log-odds (uma regressão logística 'à mão').

    Guarda a chance acumulada após cada fator (p_after_*) para a explicação mostrar
    "produto → +3 p.p., conta → +8 p.p., vendedor → -1 p.p.".
    """
    deals = deals.copy()
    base_logit = float(_logit(hist.base_rate))
    logit = np.full(len(deals), base_logit)
    for f in FACTORS:
        r = hist.rates[f]
        deals[f"p_{f}"] = deals[f].map(r["rate"]).fillna(hist.base_rate).astype(float)
        deals[f"n_{f}"] = deals[f].map(r["n"]).fillna(0).astype(int)
        logit = logit + cfg.weights[f] * (_logit(deals[f"p_{f}"]) - base_logit)
        deals[f"p_after_{f}"] = _sigmoid(logit)
    deals["p_win"] = deals[f"p_after_{FACTORS[-1]}"]
    return deals


def recommend_action(timing: str, expected_value: float, high_value: float) -> str:
    valuable = expected_value >= high_value
    if timing == "Janela de fechamento":
        return "Fechar: proposta/negociação agora" if valuable else "Fechar: empurrar o próximo passo"
    if timing == "Esfriando":
        return "Resgatar hoje (ligar, reabrir a conversa)" if valuable else "Encerrar ou limpar do pipeline"
    if timing == "Atrasando":
        return "Reengajar: agendar próximo passo esta semana"
    if timing == "Qualificar":
        return "Qualificar: confirmar conta, contato e necessidade" if valuable else "Qualificar quando sobrar tempo"
    return "Manter cadência normal"


def score_pipeline(
    pipeline: pd.DataFrame, cfg: ScoringConfig | None = None, ref_date=None
) -> ScoringResult:
    cfg = cfg or ScoringConfig()
    hist = fit_history(pipeline[pipeline["deal_stage"].isin(CLOSED_STAGES)], cfg)
    ref_date = pd.Timestamp(ref_date) if ref_date is not None else pipeline["close_date"].max()

    deals = pipeline[pipeline["deal_stage"].isin(OPEN_STAGES)].copy()
    deals = add_win_probability(deals, hist, cfg)

    # Ticket típico: mediana real dos deals ganhos > preço de tabela > mediana global
    deals["ticket"] = deals["product"].map(hist.ticket_by_product)
    if "sales_price" in deals:
        deals["ticket"] = deals["ticket"].fillna(deals["sales_price"])
    deals["ticket"] = deals["ticket"].fillna(hist.global_ticket)

    # Timing: dias aberto vs. quantis do ciclo dos deals ganhos daquele produto
    deals["days_open"] = (ref_date - deals["engage_date"]).dt.days.clip(lower=0)
    for q in ("q25", "q75", "q90"):
        deals[q] = deals["product"].map(hist.cycle_q[q]).fillna(hist.global_cycle_q[q])
    conds = [
        (deals["deal_stage"] == "Prospecting") | deals["days_open"].isna(),
        deals["days_open"] < deals["q25"],
        deals["days_open"] <= deals["q75"],
        deals["days_open"] <= deals["q90"],
    ]
    labels = ["Qualificar", "No prazo", "Janela de fechamento", "Atrasando"]
    deals["timing"] = np.select(conds, labels, default="Esfriando")
    deals["timing_factor"] = deals["timing"].map(cfg.timing_multipliers).astype(float)

    deals["expected_value"] = deals["p_win"] * deals["ticket"]
    deals["priority_value"] = deals["expected_value"] * deals["timing_factor"]
    deals["score"] = (deals["priority_value"].rank(pct=True) * 100).round().astype(int)

    high_value = float(deals["expected_value"].median())
    deals["action"] = [
        recommend_action(t, ev, high_value) for t, ev in zip(deals["timing"], deals["expected_value"])
    ]
    deals = deals.sort_values(["score", "expected_value"], ascending=False).reset_index(drop=True)
    return ScoringResult(deals, hist, cfg, ref_date, high_value)


# --------------------------------------------------------------------------- explicação
def explain(deal: pd.Series, result: ScoringResult) -> list[str]:
    """Explicação em linguagem de vendedor, na mesma ordem em que o score é construído."""
    base, cfg = result.history.base_rate, result.cfg

    def pp(after: float, before: float) -> str:
        return f"{(after - before) * 100:+.0f} p.p."

    lines = [f"**Ponto de partida**: {base:.0%} dos deals fechados do histórico foram ganhos."]
    lines.append(
        f"**Produto {deal['product']}**: fecha {deal['p_product']:.0%} das vezes "
        f"({int(deal['n_product'])} deals fechados) → {pp(deal['p_after_product'], base)}"
    )
    if pd.isna(deal["account"]):
        lines.append("**Conta**: não preenchida no CRM → sem ajuste. Preencher a conta melhora a previsão.")
    elif deal["n_account"] == 0:
        lines.append(f"**Conta {deal['account']}**: ainda sem histórico fechado → sem ajuste.")
    else:
        lines.append(
            f"**Conta {deal['account']}**: {deal['p_account']:.0%} de conversão "
            f"({int(deal['n_account'])} deals) → {pp(deal['p_after_account'], deal['p_after_product'])}"
        )
    lines.append(
        f"**Vendedor {deal['sales_agent']}**: {deal['p_sales_agent']:.0%} de conversão "
        f"({int(deal['n_sales_agent'])} deals; peso {cfg.w_agent:g}) → {pp(deal['p_win'], deal['p_after_account'])}"
    )
    lines.append(f"➡️ **Chance de fechar: {deal['p_win']:.0%}**")
    if deal["timing"] == "Qualificar":
        lines.append(
            f"**Timing**: ainda em Prospecting (sem data de engajamento) → *{deal['timing']}* ×{deal['timing_factor']:g}"
        )
    else:
        lines.append(
            f"**Timing**: {int(deal['days_open'])} dias aberto. Deals ganhos de {deal['product']} fecham "
            f"entre {deal['q25']:.0f} e {deal['q75']:.0f} dias (metade central; 90% até {deal['q90']:.0f}) "
            f"→ *{deal['timing']}* ×{deal['timing_factor']:g}"
        )
    lines.append(f"**Ticket típico**: US$ {deal['ticket']:,.0f} (mediana dos deals ganhos deste produto)")
    lines.append(
        f"**Valor esperado**: {deal['p_win']:.0%} × US$ {deal['ticket']:,.0f} = US$ {deal['expected_value']:,.0f}"
        f" → com timing: US$ {deal['priority_value']:,.0f}"
    )
    lines.append(
        f"➡️ **Score {int(deal['score'])}**: entre os {max(1, 100 - int(deal['score']))}% melhores deals abertos do pipeline."
    )
    return lines


def team_summary(deals: pd.DataFrame) -> pd.DataFrame:
    """Visão do manager: carga e saúde do pipeline por vendedor."""
    out = (
        deals.groupby(["regional_office", "manager", "sales_agent"], dropna=False)
        .agg(
            deals=("opportunity_id", "count"),
            valor_esperado=("expected_value", "sum"),
            chance_media=("p_win", "mean"),
            na_janela=("timing", lambda s: int((s == "Janela de fechamento").sum())),
            esfriando=("timing", lambda s: int((s == "Esfriando").sum())),
            sem_conta=("account", lambda s: int(s.isna().sum())),
        )
        .reset_index()
    )
    return out.sort_values("valor_esperado", ascending=False)


# --------------------------------------------------------------------------- validação
def backtest(pipeline: pd.DataFrame, cfg: ScoringConfig | None = None, cutoff=None) -> dict:
    """Aprende com deals fechados antes do cutoff e avalia a chance de fechar nos fechados depois."""
    cfg = cfg or ScoringConfig()
    closed = pipeline[pipeline["deal_stage"].isin(CLOSED_STAGES)].dropna(subset=["close_date"])
    cutoff = pd.Timestamp(cutoff) if cutoff is not None else closed["close_date"].quantile(0.7)
    train, test = closed[closed["close_date"] < cutoff], closed[closed["close_date"] >= cutoff]
    hist = fit_history(train, cfg)
    scored = add_win_probability(test, hist, cfg)

    y = (scored["deal_stage"] == "Won").astype(int).to_numpy()
    p = scored["p_win"].to_numpy()
    ranks = pd.Series(p).rank().to_numpy()  # AUC via Mann-Whitney, sem sklearn
    n_pos, n_neg = y.sum(), len(y) - y.sum()
    auc = (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return {
        "cutoff": cutoff.date().isoformat(),
        "train": int(len(train)),
        "test": int(len(test)),
        "auc": float(auc),
        "brier": float(np.mean((p - y) ** 2)),
        "brier_base": float(np.mean((hist.base_rate - y) ** 2)),
    }


if __name__ == "__main__":
    res = score_pipeline(load_data())
    out = Path(__file__).resolve().parent / "scored_pipeline.csv"
    res.deals.to_csv(out, index=False)
    print(f"{len(res.deals)} deals abertos scorados (referência {res.ref_date.date()}) → {out}")
```

---

## `app.py`

```python
"""Lead Scorer — app do vendedor. Rode: streamlit run app.py"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from scoring import DATA_DIR, ScoringConfig, explain, load_data, score_pipeline, team_summary

st.set_page_config(page_title="Lead Scorer", page_icon="🎯", layout="wide")

COLS = {
    "score": "Score",
    "account": "Conta",
    "product": "Produto",
    "sales_agent": "Vendedor",
    "deal_stage": "Stage",
    "days_open": "Dias aberto",
    "chance": "Chance",
    "ticket": "Ticket (US$)",
    "expected_value": "Valor esperado (US$)",
    "timing": "Timing",
    "action": "Ação sugerida",
    "opportunity_id": "ID",
}
COLUMN_CONFIG = {
    "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
    "Chance": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%"),
    "Ticket (US$)": st.column_config.NumberColumn(format="%d"),
    "Valor esperado (US$)": st.column_config.NumberColumn(format="%d"),
    "Dias aberto": st.column_config.NumberColumn(format="%d"),
}


@st.cache_data(show_spinner="Lendo o CRM...")
def get_data() -> pd.DataFrame:
    return load_data()


@st.cache_data(show_spinner="Calculando scores...")
def get_scores(ref_date: str, w_agent: float, boost: float, penalty: float, k: float):
    cfg = ScoringConfig(w_agent=w_agent, shrinkage_k=k)
    cfg.timing_multipliers["Janela de fechamento"] = boost
    cfg.timing_multipliers["Esfriando"] = penalty
    return score_pipeline(get_data(), cfg, ref_date=ref_date)


def show_table(df: pd.DataFrame) -> None:
    t = df.assign(
        chance=(df["p_win"] * 100).round().astype(int),
        account=df["account"].fillna("(sem conta)"),
    )
    t = t[list(COLS)].rename(columns=COLS)
    st.dataframe(t, hide_index=True, use_container_width=True, column_config=COLUMN_CONFIG)


def deal_label(r: pd.Series) -> str:
    acc = r["account"] if pd.notna(r["account"]) else "(sem conta)"
    return f"[{int(r['score'])}] {acc} · {r['product']} · {r['sales_agent']}"


def show_deal(deal: pd.Series, result) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", int(deal["score"]))
    c2.metric("Chance de fechar", f"{deal['p_win']:.0%}")
    c3.metric("Valor esperado", f"US$ {deal['expected_value']:,.0f}")
    c4.metric("Dias aberto", "—" if pd.isna(deal["days_open"]) else int(deal["days_open"]))
    st.info(f"**Ação sugerida:** {deal['action']}")
    st.markdown("**Por que esse score?**")
    for line in explain(deal, result):
        st.markdown(f"- {line}")
    extras = {k: deal.get(k) for k in ("sector", "revenue", "employees") if pd.notna(deal.get(k))}
    if extras:
        st.caption("Sobre a conta: " + " · ".join(f"{k}: {v}" for k, v in extras.items()))


# ------------------------------------------------------------------ dados
try:
    raw = get_data()
except FileNotFoundError as e:
    st.error(f"Não encontrei os CSVs em `{DATA_DIR}`. Veja o README (Setup). Detalhe: {e}")
    st.stop()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("🎯 Lead Scorer")
ref_date = st.sidebar.date_input(
    "Data de referência ('hoje')",
    value=raw["close_date"].max().date(),
    help="O dataset termina em dez/2017; a última data do CRM faz o tempo no pipeline fazer sentido.",
)
offices = sorted(raw["regional_office"].dropna().unique())
office = st.sidebar.selectbox("Escritório", ["Todos"] + offices)
team = raw if office == "Todos" else raw[raw["regional_office"] == office]
managers = sorted(team["manager"].dropna().unique())
manager = st.sidebar.selectbox("Manager", ["Todos"] + managers)
team = team if manager == "Todos" else team[team["manager"] == manager]
agents = sorted(team["sales_agent"].dropna().unique())
agent = st.sidebar.selectbox("Vendedor", ["Todos"] + agents)
top_n = st.sidebar.slider("Quantos deals mostrar", 10, 200, 25, 5)

with st.sidebar.expander("⚙️ Ajustes (RevOps)"):
    w_agent = st.slider("Peso do histórico do vendedor", 0.0, 1.0, 0.5, 0.1)
    boost = st.slider("Boost: janela de fechamento", 1.0, 1.5, 1.2, 0.05)
    penalty = st.slider("Penalidade: esfriando", 0.2, 1.0, 0.6, 0.05)
    k = st.slider("Shrinkage (deals que 'valem' a média)", 5, 100, 20, 5)

result = get_scores(ref_date.isoformat(), w_agent, boost, penalty, float(k))
view = result.deals
if office != "Todos":
    view = view[view["regional_office"] == office]
if manager != "Todos":
    view = view[view["manager"] == manager]
if agent != "Todos":
    view = view[view["sales_agent"] == agent]

# ------------------------------------------------------------------ cabeçalho
who = agent if agent != "Todos" else (manager if manager != "Todos" else office)
st.title(f"Onde focar hoje — {who}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Deals abertos", len(view))
c2.metric("Valor esperado", f"US$ {view['expected_value'].sum():,.0f}")
c3.metric("Na janela de fechamento", int((view["timing"] == "Janela de fechamento").sum()))
c4.metric("Esfriando", int((view["timing"] == "Esfriando").sum()))

if view.empty:
    st.warning("Nenhum deal aberto para esse filtro.")
    st.stop()

tab_prio, tab_rescue, tab_qual, tab_team, tab_how = st.tabs(
    ["🎯 Prioridades", "🔥 Resgate", "🧭 Qualificar", "📊 Time", "ℹ️ Como funciona"]
)

with tab_prio:
    st.caption("Score = posição do deal no pipeline aberto, combinando chance de fechar, ticket e timing.")
    show_table(view.head(top_n))
    st.download_button(
        "⬇️ Baixar lista (CSV)",
        view.to_csv(index=False).encode("utf-8"),
        file_name="prioridades.csv",
        mime="text/csv",
    )
    st.divider()
    st.subheader("Por que esse score?")
    top = view.head(top_n)
    labels = dict(zip(top["opportunity_id"], top.apply(deal_label, axis=1)))
    chosen = st.selectbox("Escolha um deal", list(labels), format_func=labels.get)
    show_deal(view[view["opportunity_id"] == chosen].iloc[0], result)

with tab_rescue:
    st.subheader("Deals esfriando ou atrasando")
    st.caption("Passaram do ciclo normal do produto. Os de maior valor esperado merecem uma ligação hoje; os demais, limpar o pipeline.")
    rescue = view[view["timing"].isin(["Esfriando", "Atrasando"])].sort_values("expected_value", ascending=False)
    show_table(rescue)

with tab_qual:
    st.subheader("Prospecting: o que vale qualificar primeiro")
    st.caption("Ainda sem engajamento. Ordenado pelo que pode virar receita, se qualificado.")
    show_table(view[view["timing"] == "Qualificar"].sort_values("expected_value", ascending=False))

with tab_team:
    st.subheader("Mapa do pipeline")
    chart_df = view[["opportunity_id", "account", "product", "sales_agent", "score", "p_win", "ticket", "timing", "days_open"]].copy()
    chart_df["account"] = chart_df["account"].fillna("(sem conta)")
    scatter = (
        alt.Chart(chart_df)
        .mark_circle(opacity=0.65)
        .encode(
            x=alt.X("p_win:Q", title="Chance de fechar", axis=alt.Axis(format="%")),
            y=alt.Y("ticket:Q", title="Ticket típico (US$)", scale=alt.Scale(type="log")),
            color=alt.Color("timing:N", title="Timing"),
            size=alt.Size("score:Q", legend=None),
            tooltip=[
                "opportunity_id", "account", "product", "sales_agent", "score",
                alt.Tooltip("p_win:Q", format=".0%", title="chance"), "days_open", "timing",
            ],
        )
        .interactive()
    )
    st.altair_chart(scatter, use_container_width=True)
    st.subheader("Por vendedor")
    st.dataframe(
        team_summary(view),
        hide_index=True,
        use_container_width=True,
        column_config={
            "valor_esperado": st.column_config.NumberColumn("Valor esperado (US$)", format="%d"),
            "chance_media": st.column_config.NumberColumn("Chance média", format="%.0%"),
        },
    )

with tab_how:
    h = result.history
    st.markdown(
        f"""
**Score = percentil de `Chance × Ticket × Timing` entre os {len(result.deals)} deals abertos.**
Score 85 significa: melhor que 85% do pipeline aberto.

- **Chance de fechar**: começa na taxa base ({h.base_rate:.0%} dos deals fechados foram ganhos) e é
  ajustada pelo histórico do **produto**, da **conta** e do **vendedor** (peso {result.cfg.w_agent:g}).
  Grupos com poucos deals são puxados para a média (shrinkage k={result.cfg.shrinkage_k:g}).
- **Ticket**: mediana do que os deals ganhos daquele produto realmente fecharam (não o preço de tabela).
- **Timing**: compara os dias em aberto com o ciclo dos deals ganhos do mesmo produto —
  *Janela de fechamento* (p25–p75) ×{result.cfg.timing_multipliers['Janela de fechamento']:g},
  *Atrasando* (p75–p90) ×{result.cfg.timing_multipliers['Atrasando']:g},
  *Esfriando* (>p90) ×{result.cfg.timing_multipliers['Esfriando']:g},
  *Qualificar* (Prospecting) ×{result.cfg.timing_multipliers['Qualificar']:g}.

Referência por produto (aprendida do histórico):
"""
    )
    ref = (
        h.rates["product"][["n", "rate"]]
        .join(h.ticket_by_product.rename("ticket"))
        .join(h.cycle_q)
        .reset_index()
        .rename(columns={"product": "Produto", "n": "Deals fechados", "rate": "Conversão", "ticket": "Ticket (US$)",
                         "q25": "Ciclo p25 (dias)", "q75": "Ciclo p75 (dias)", "q90": "Ciclo p90 (dias)"})
    )
    st.dataframe(
        ref, hide_index=True, use_container_width=True,
        column_config={"Conversão": st.column_config.NumberColumn(format="%.0%"),
                       "Ticket (US$)": st.column_config.NumberColumn(format="%d")},
    )
```

---

## `cli.py`

```python
"""Lead Scorer no terminal. Ex.: python cli.py --agent "Darcel Schlecht" --top 10"""
from __future__ import annotations

import argparse

import pandas as pd

from scoring import explain, load_data, score_pipeline

COLS = ["score", "account", "product", "sales_agent", "deal_stage", "days_open", "p_win",
        "ticket", "expected_value", "timing", "action", "opportunity_id"]
FMT = {
    "p_win": "{:.0%}".format,
    "ticket": "{:,.0f}".format,
    "expected_value": "{:,.0f}".format,
    "days_open": lambda x: "-" if pd.isna(x) else f"{x:.0f}",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Prioridades do pipeline (Lead Scorer)")
    ap.add_argument("--agent")
    ap.add_argument("--manager")
    ap.add_argument("--office")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--explain", type=int, default=3, help="quantos deals do topo explicar")
    ap.add_argument("--ref-date", help="'hoje' (YYYY-MM-DD); padrão = última data do dataset")
    ap.add_argument("--csv", help="salvar o pipeline filtrado e scorado neste arquivo")
    args = ap.parse_args()

    result = score_pipeline(load_data(), ref_date=args.ref_date)
    df = result.deals
    for col, val in (("sales_agent", args.agent), ("manager", args.manager), ("regional_office", args.office)):
        if val:
            df = df[df[col] == val]
    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"salvo: {args.csv}")

    print(f"\nReferência: {result.ref_date.date()} · {len(df)} deals abertos · taxa base {result.history.base_rate:.0%}\n")
    top = df.head(args.top)
    print(top[COLS].to_string(index=False, na_rep="-", formatters=FMT))

    for _, row in top.head(args.explain).iterrows():
        acc = row["account"] if pd.notna(row["account"]) else "(sem conta)"
        print(f"\n=== {row['opportunity_id']} · {acc} · {row['product']} · {row['sales_agent']} · score {row['score']}")
        for line in explain(row, result):
            print("  - " + line.replace("**", "").replace("*", ""))


if __name__ == "__main__":
    main()
```

## `backtest.py`

```python
"""Valida a 'chance de fechar' fora da amostra (split temporal: aprende no passado, testa no futuro)."""
from scoring import backtest, load_data

if __name__ == "__main__":
    m = backtest(load_data())
    print(f"Treino: {m['train']} deals fechados antes de {m['cutoff']} · Teste: {m['test']} depois")
    print(f"AUC: {m['auc']:.3f}  (0.5 = chute; quanto maior, melhor separa Won de Lost)")
    print(f"Brier: {m['brier']:.4f} vs. chutar a taxa base: {m['brier_base']:.4f}  (menor é melhor)")
```

## `test_scoring.py`

```python
"""Testes rápidos da lógica (pytest -q)."""
import numpy as np
import pandas as pd
import pytest

from scoring import ScoringConfig, explain, score_pipeline, smoothed_win_rate


def make_pipeline(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    products = {"Alpha": (1000, 0.8), "Beta": (100, 0.4)}  # ticket, taxa de win
    rows = []
    for i in range(400):
        product = "Alpha" if i % 2 == 0 else "Beta"
        ticket, p = products[product]
        won = rng.random() < p
        engage = pd.Timestamp("2017-01-01") + pd.Timedelta(days=int(rng.integers(0, 200)))
        close = engage + pd.Timedelta(days=int(rng.integers(20, 80)))
        rows.append(dict(opportunity_id=f"C{i}", sales_agent=f"agent{i % 3}", product=product,
                         account=f"acc{i % 5}", deal_stage="Won" if won else "Lost",
                         engage_date=engage, close_date=close, close_value=ticket if won else 0))
    rows += [
        dict(opportunity_id="O1", sales_agent="agent0", product="Alpha", account="acc0", deal_stage="Engaging",
             engage_date=pd.Timestamp("2017-11-20"), close_date=pd.NaT, close_value=np.nan),
        dict(opportunity_id="O2", sales_agent="agent0", product="Beta", account="acc0", deal_stage="Engaging",
             engage_date=pd.Timestamp("2017-11-20"), close_date=pd.NaT, close_value=np.nan),
        dict(opportunity_id="O3", sales_agent="agent1", product="Alpha", account=None, deal_stage="Prospecting",
             engage_date=pd.NaT, close_date=pd.NaT, close_value=np.nan),
        dict(opportunity_id="O4", sales_agent="agent2", product="Alpha", account="acc1", deal_stage="Engaging",
             engage_date=pd.Timestamp("2017-01-05"), close_date=pd.NaT, close_value=np.nan),
    ]
    df = pd.DataFrame(rows)
    df["manager"], df["regional_office"] = "M", "Central"
    df["sales_price"] = df["product"].map({"Alpha": 1000, "Beta": 100})
    return df


@pytest.fixture
def result():
    return score_pipeline(make_pipeline(), ref_date="2017-12-01")


def test_shrinkage_pulls_small_groups_to_base():
    closed = pd.DataFrame({"g": ["a"] * 2 + ["b"] * 200, "won": [1, 1] + [1] * 100 + [0] * 100})
    r = smoothed_win_rate(closed, "g", base_rate=0.5, k=20)
    assert 0.5 < r.loc["a", "rate"] < 0.7  # 2 wins em 2 deals não viram 100%
    assert abs(r.loc["b", "rate"] - 0.5) < 0.01


def test_bounds(result):
    d = result.deals
    assert d["p_win"].between(0, 1).all()
    assert d["score"].between(0, 100).all()
    assert d["score"].max() == 100


def test_better_product_scores_higher(result):
    d = result.deals.set_index("opportunity_id")
    assert d.loc["O1", "p_win"] > d.loc["O2", "p_win"]
    assert d.loc["O1", "score"] > d.loc["O2", "score"]


def test_timing_labels(result):
    d = result.deals.set_index("opportunity_id")
    assert d.loc["O3", "timing"] == "Qualificar"
    assert d.loc["O4", "timing"] == "Esfriando"
    assert d.loc["O4", "timing_factor"] == ScoringConfig().timing_multipliers["Esfriando"]


def test_explain_mentions_key_pieces(result):
    d = result.deals.set_index("opportunity_id")
    text = " ".join(explain(d.loc["O1"], result))
    assert "Produto Alpha" in text and "Score" in text and "Timing" in text
```

## `requirements.txt`

```
pandas>=2.0
numpy>=1.24
streamlit>=1.36,<1.50
altair>=5.0
pytest>=7.0
```

---

## `README.md`

````markdown
# Lead Scorer — onde focar hoje

Ferramenta para o vendedor abrir na segunda de manhã e saber em quais deals gastar tempo.
Cada deal aberto ganha um **Score (0–100)**, uma **chance de fechar**, um **status de timing**
e uma **ação sugerida** — e um painel "por que esse score?" que explica a conta em português.

## Setup

```bash
git clone <repo> && cd lead-scorer
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Dados: baixe do Kaggle e coloque os 4 CSVs em data/
#   https://www.kaggle.com/datasets/agungpambudi/crm-sales-predictive-analytics
# ou, com a CLI do Kaggle configurada:
kaggle datasets download -d agungpambudi/crm-sales-predictive-analytics --unzip -p data

streamlit run app.py          # abre em http://localhost:8501
```

Outras formas de usar:

```bash
python cli.py --agent "Darcel Schlecht" --top 10      # lista + explicação no terminal
python cli.py --manager "Melvin Marxen" --csv time.csv
python scoring.py                                     # gera scored_pipeline.csv (importar no CRM)
python backtest.py                                    # valida a chance de fechar fora da amostra
pytest -q                                             # testes
```

Requer Python 3.10+.

## Como o vendedor usa

1. Filtra por escritório → manager → vendedor na barra lateral.
2. Aba **Prioridades**: os N deals com maior score, com ação sugerida. Clica em um deal e vê
   o "por quê" linha a linha.
3. Aba **Resgate**: deals que passaram do ciclo normal — ligar hoje ou limpar o pipeline.
4. Aba **Qualificar**: prospecting ordenado pelo que vale qualificar primeiro.
5. Aba **Time** (para managers): mapa chance × ticket e carga/saúde do pipeline por vendedor.
6. Botão "Baixar CSV" leva a lista para o CRM/planilha.

## Lógica de scoring

```
Chance de fechar  = f(histórico do produto, da conta, do vendedor)
Ticket típico     = mediana do close_value dos deals GANHOS do produto
Timing            = multiplicador pelo tempo em aberto vs. ciclo típico do produto
Prioridade        = Chance × Ticket × Timing
Score (0–100)     = percentil da Prioridade entre todos os deals abertos
```

**Por que esses critérios**

| Critério | Como é calculado | Por quê |
|---|---|---|
| Produto | Taxa Won/(Won+Lost) histórica do produto, suavizada | Maior driver tanto de conversão quanto de valor. Um GTK 500 e um MG Special são jogos diferentes. |
| Conta | Taxa histórica da conta, suavizada | Relacionamento: conta que já comprou 70% das vezes tende a comprar de novo. É o fator que mais diferencia deals do *mesmo* produto. Se a conta está vazia no CRM (muitos deals em Engaging estão), o fator fica neutro e a explicação pede para preencher. |
| Vendedor | Taxa histórica do vendedor, suavizada, **peso 0,5** | Execução importa, mas não deve dominar nem "punir" o vendedor na própria tela; o peso é um slider para RevOps. |
| Timing | Dias em aberto vs. quantis (p25/p75/p90) do ciclo dos deals ganhos do mesmo produto | Cada produto tem um ritmo. Na *janela* (p25–p75) é quando a maioria fecha → ×1,2, agir agora. Além do p90 quase nenhum deal ganho demorou tanto → ×0,6, vai para a aba Resgate. Prospecting sem engajamento → ×0,8. |
| Ticket | Mediana real dos deals ganhos, não o preço de tabela | O que fecha na prática difere do catálogo; usar dinheiro real evita superestimar. |

**Detalhes que fazem o número ser confiável**

- *Shrinkage*: `rate = (wins + k·base) / (n + k)`, k=20. Um vendedor novo com 2 wins em 2 deals não vira "100%"; fica perto da média até acumular histórico.
- *Combinação em log-odds*: os fatores somam desvios em relação à taxa base no espaço de logit (como uma regressão logística feita à mão) — evita que multiplicar taxas gere probabilidades absurdas e permite pesos por fator.
- *Explicabilidade por construção*: a chance acumulada é guardada após cada fator, então o painel mostra "produto → +3 p.p., conta → +8 p.p., vendedor → −1 p.p.", na mesma ordem em que o score é calculado.
- *Score relativo*: percentil no pipeline aberto. "Score 85" = melhor que 85% dos deals abertos. É estável para o vendedor entender e não exige calibrar uma escala absoluta.
- *Validação*: `python backtest.py` aprende nos deals fechados antes de um corte temporal e mede AUC e Brier nos fechados depois, comparando com chutar a taxa base. Se a chance de fechar não bater a taxa base, o problema está nos fatores, não na interface.

**Por que não é "só ordenar por valor"**: um GTK 500 esfriando com conta de conversão ruim cai
para a aba Resgate com ação "ligar hoje ou encerrar", enquanto um GTX Plus Pro de conta boa e na janela
de fechamento sobe para o topo. O valor pesa — é receita — mas chance e timing reordenam e, principalmente,
mudam a *ação*.

**Correções de dados aplicadas**: `GTXPro` → `GTX Pro` (typo do pipeline vs. catálogo); espaços
extras em chaves; datas e valores forçados para tipo correto; deals sem conta tratados como neutros.

## Limitações e o que falta para escalar

- **Dataset estático (2017)**: a "data de referência" é manual (padrão = última data do CRM). Em produção seria `hoje`, com scoring recalculado toda noite.
- **Sem sinais de engajamento**: o CRM não tem e-mails, reuniões, respostas. É o próximo fator mais valioso a incluir.
- **Timing é heurístico**: compara deals abertos (censurados) com o ciclo de deals já fechados. É útil e explicável, mas não é um modelo de sobrevivência.
- **Chance não é calibrada por ML**: é uma combinação de taxas com pesos fixos. Com mais features, o passo natural é uma regressão logística/GBM calibrada, mantendo o mesmo painel de explicação (contribuições por fator).
- **Risco de profecia autorrealizável**: fatores por conta/vendedor podem reforçar vieses históricos. Por isso o peso do vendedor é baixo e ajustável, e há o backtest para monitorar.
- **Score relativo**: muda quando o pipeline muda. Bom para priorizar, ruim para meta absoluta.
- **Sem persistência**: não guarda histórico de scores, "snooze", feedback do vendedor ("esse score está errado"), nem escreve de volta no CRM.
- **Para escalar**: conector com o CRM (API), job agendado, tabela de scores com histórico, botão de feedback, digest por Slack/e-mail na segunda de manhã, autenticação por vendedor, monitoramento de drift via backtest recorrente.
````

---

## `PROCESS_LOG.md`

```markdown
# Process log — Challenge 003 Lead Scorer

**Ferramenta:** Claude Code (modelo Opus 5), sessão de 2026-09-16, modo somente texto
(sem acesso a arquivos, internet ou execução). Todo o código, README e este log foram
gerados na conversa e revisados por leitura, não executados pelo agente.

## 1. Prompt inicial
Colei o enunciado completo do challenge (contexto, dados, entregáveis, critérios, dicas)
com a instrução "Resolva o desafio. Entregue a solução completa (código e explicação da
lógica de scoring)".

## 2. O que o agente fez, na ordem
1. **Recuperou a estrutura do dataset de memória** (é o dataset CRM Sales Opportunities da
   Maven, republicado no Kaggle): colunas de cada CSV, ~2.089 deals abertos, `account`
   vazio em boa parte deles, Prospecting sem `engage_date`, e o typo `GTXPro` no pipeline.
   → Gerou o `PRODUCT_FIXES` e o tratamento de conta nula.
2. **Escolheu a arquitetura**: Streamlit + módulo `scoring.py` isolado (para testar e reutilizar
   em CLI/CSV), sem banco, sem ML pesado. Justificativa: a Head pediu "algo que o vendedor abra",
   e o critério "outro dev consegue manter" favorece um arquivo de lógica pequeno e testável.
3. **Desenhou o scoring** considerando três alternativas:
   - ordenar por valor — descartado (proibido pelo enunciado e ignora chance/timing);
   - XGBoost sobre features — descartado (poucas features reais, sem explicação nativa, esforço
     de calibração fora do time budget);
   - taxas históricas com shrinkage combinadas em log-odds + heurística de timing — escolhido:
     explicável por construção, tunável por RevOps, validável com backtest.
   Decisões pontuais: peso 0,5 para o vendedor (fairness/adoção), ticket pela mediana real dos
   deals ganhos, score como percentil (fácil de ler), aba separada para deals esfriando.
4. **Gerou o código** (scoring, app, CLI, backtest, testes) e a documentação.
5. **Revisou por leitura** os pontos de maior risco: aritmética com `NaT`/`NaN` em `days_open`,
   `np.select` com Series, `fillna` de quantis por produto, cache do Streamlit com dataclasses,
   formatação em `column_config`.

## 3. O que NÃO foi feito pelo agente (e precisa ser feito por mim ao rodar)
- Executar `pytest -q`, `python backtest.py` e `streamlit run app.py` e registrar as saídas aqui.
- Conferir se os nomes de colunas dos CSVs baixados batem com o esperado
  (`opportunity_id, sales_agent, product, account, deal_stage, engage_date, close_date, close_value`).
- Conferir os quantis de ciclo por produto na aba "Como funciona" e ajustar os multiplicadores
  de timing se a janela ficar estranha para algum produto.
- Anexar screenshots das abas e o resultado do backtest.

## 4. Iterações previstas (prompts seguintes)
- "O backtest deu AUC X; quais fatores tirar/adicionar?" 
- "Adiciona o setor da conta como fator e mostra se melhora o Brier."
- "Gera um digest semanal em Markdown por vendedor para mandar no Slack."
```

---

## O que conferir ao rodar pela primeira vez

1. `pytest -q` — testes usam dados sintéticos, não dependem do Kaggle.
2. `python backtest.py` — espero AUC modesto (algo entre 0,55 e 0,65: só há 3 fatores categóricos) e Brier menor que a base. Se a AUC ficar ≤ 0,5, o problema está nas taxas por fator (verifique se `GTXPro` foi corrigido e se `deal_stage` tem exatamente `Won`/`Lost`).
3. Aba **Como funciona** — a tabela por produto deve mostrar 7 produtos, tickets próximos aos preços de tabela e ciclos de ~30–90 dias. Se aparecer um 8º produto "GTXPro", a correção não pegou.
4. Se sua versão do Streamlit for ≥ 1.50 e reclamar de `use_container_width`, troque por `width="stretch"` nas chamadas de `st.dataframe`/`st.altair_chart` (o `requirements.txt` já pina `<1.50` para evitar isso).
