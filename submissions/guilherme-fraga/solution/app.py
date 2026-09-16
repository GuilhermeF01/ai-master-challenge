"""Lead Scorer — o que o vendedor abre na segunda de manhã.

Rodar (a partir de solution/):
    streamlit run app.py

Sem API key, sem rede: calcula tudo dos CSVs em data/ usando lead_scorer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from lead_scorer import ScoringConfig, calibrate, load_crm, score_open_deals, split_pipeline  # noqa: E402

st.set_page_config(page_title="Lead Scorer — fila de atenção", page_icon="🎯", layout="wide")

TODOS = "Todos"
AVISO = ("**O score é uma fila de atenção, não probabilidade de fechar.** "
         "Ele diz onde o seu tempo faz diferença hoje — um deal com score 90 não tem 90% de chance.")


# ---------------------------------------------------------------------------
# Dados (cacheados: calcula uma vez por sessão do servidor)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Calculando a fila a partir do CRM…")
def carregar() -> tuple[pd.DataFrame, dict]:
    crm = load_crm()
    closed, open_deals = split_pipeline(crm.pipeline)
    calib = calibrate(closed, crm.products, open_deals=open_deals)
    scored = score_open_deals(open_deals, calib, crm.teams, crm.accounts)
    meta = {
        "referencia": scored.attrs["reference_date"],
        "parede": calib.wall_days,
        "win_rate": calib.global_rate,
        "n_fechados": calib.n_closed,
        "degraus": " · ".join(f"{int(z.lo)} a {int(z.hi)} dias: {int(z.f2)}" for z in calib.zones.itertuples()),
        "pesos": (calib.config.w_f2, calib.config.w_f1, calib.config.w_f3),
        "teams": crm.teams,
    }
    return scored, meta


def usd(x: float) -> str:
    return "USD " + f"{int(round(x)):,}".replace(",", ".")


def n(x: int) -> str:
    return f"{int(x):,}".replace(",", ".")


def resumo_categorias(df: pd.DataFrame) -> dict[str, int]:
    c = df["categoria"].value_counts()
    return {k: int(c.get(k, 0)) for k in ("Agir", "Engajar", "Decidir")}


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------


def faixa_pipeline(df: pd.DataFrame, meta: dict, escopo: str) -> None:
    """O achado principal, na cara: quanto do pipeline está além da parede."""
    r = resumo_categorias(df)
    engaging = df["stage"].eq("Engaging").sum()
    pct_parede = r["Decidir"] / engaging if engaging else 0.0
    valor_parado = df.loc[df["categoria"] == "Decidir", "valor_produto"].sum()

    sem_conta = int(df["conta"].isna().sum())
    pct_sem_conta = sem_conta / len(df) if len(df) else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Agir (Engaging até %d dias)" % meta["parede"], n(r["Agir"]))
    c2.metric("Engajar (Prospecting)", n(r["Engajar"]))
    c3.metric("Decidir (passou da parede)", n(r["Decidir"]))
    c4.metric("Engaging além da parede", f"{pct_parede:.0%}")
    c5.metric("Sem conta no CRM", n(sem_conta), f"{pct_sem_conta:.0%} dos {n(len(df))} abertos",
              delta_color="off", help="Deal aberto sem `account` preenchido. O score não depende de conta "
              "(nenhum fator usa accounts.csv), mas o vendedor não sabe com quem está falando.")
    if r["Decidir"] > r["Agir"]:
        st.error(
            f"**{escopo}: a lista de decisão é maior que a fila de trabalho.** "
            f"{n(r['Decidir'])} deals em Engaging há mais de {meta['parede']} dias — nenhum deal do histórico "
            f"fechou depois disso. São {usd(valor_parado)} em preço de tabela parados esperando uma decisão "
            f"(requalificar ou descartar), contra {n(r['Agir'])} deals onde esforço ainda muda o resultado."
        )


def cartao_deal(pos: int, d: pd.Series, mostrar_vendedor: bool = False) -> None:
    """Um deal como cartão: score grande, contexto, e as três frases."""
    with st.container(border=True):
        esq, dir_ = st.columns([1, 3])
        with esq:
            if pd.notna(d["score"]):
                st.markdown(f"<div style='font-size:2.4rem;font-weight:700;line-height:1'>{d['score']:.0f}</div>"
                            f"<div style='opacity:.7'>score · #{pos}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='font-size:1.6rem;font-weight:700'>Decidir</div>", unsafe_allow_html=True)
            st.caption(f"confiança **{d['confianca']}** · {d['n_celula']} deals seus em {d['produto']}")
        with dir_:
            titulo = f"**{d['produto']}** · {d['conta'] if pd.notna(d['conta']) else '_sem conta no CRM_'}"
            if mostrar_vendedor:
                titulo += f" · {d['vendedor']}"
            st.markdown(titulo)
            tags = [f"`{d['categoria']}`"]
            if pd.notna(d["idade_dias"]):
                tags.append(f"{int(d['idade_dias'])} dias em Engaging")
            if pd.notna(d["marcadores"]):
                tags.append(f"**{d['marcadores']}**")
            tags.append(usd(d["valor_produto"]))
            st.caption(" · ".join(tags))
            st.markdown(f"{_seta(d['F2'])} {d['frase_F2']}")
            st.markdown(f"{_seta(d['F1'])} {d['frase_F1']}")
            st.markdown(f"{_seta(d['F3'])} {d['frase_F3']}")


def _quantos(total: int, minimo: int, padrao: int, key: str) -> int:
    """Slider de quantos cartões mostrar; sem slider quando não há o que escolher."""
    if total <= minimo:
        return total
    return st.slider("Quantos mostrar", minimo, total, min(padrao, total), key=key)


def _seta(f: float) -> str:
    if pd.isna(f):
        return "▫️"
    return "🟢" if f >= 65 else "🟡" if f >= 40 else "🔴"


def tabela(df: pd.DataFrame, colunas: list[str]) -> None:
    mostrar = df[colunas].copy()
    for c in ("conta", "marcadores"):
        if c in mostrar:
            mostrar[c] = mostrar[c].fillna("—")
    st.dataframe(
        mostrar,
        hide_index=True,
        width="stretch",
        column_config={
            "score": st.column_config.NumberColumn("score", format="%.0f"),
            "valor_produto": st.column_config.NumberColumn("valor (USD)", format="%d"),
            "idade_dias": st.column_config.NumberColumn("dias", format="%d"),
            "engage_date": st.column_config.DateColumn("engajado em"),
            "F1": st.column_config.NumberColumn("F1 encaixe", format="%.0f"),
            "F2": st.column_config.NumberColumn("F2 atenção", format="%.0f"),
            "F3": st.column_config.NumberColumn("F3 valor", format="%.0f"),
        },
    )


COLS_TABELA = ["opportunity_id", "categoria", "score", "produto", "conta", "idade_dias", "valor_produto",
               "confianca", "marcadores", "F1", "F2", "F3", "frase_F1", "frase_F2", "frase_F3"]


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------


def tela_vendedor(df: pd.DataFrame, meta: dict, vendedores: list[str]) -> None:
    opcoes = ["— escolha seu nome —"] + vendedores
    # ?vendedor=Nome na URL pré-seleciona: cada vendedor pode salvar o próprio link
    pre = st.query_params.get("vendedor")
    nome = st.selectbox("Quem é você?", opcoes, index=opcoes.index(pre) if pre in opcoes else 0, key="vendedor")
    if nome not in vendedores:
        st.info("Escolha seu nome para ver a sua fila de hoje.")
        return

    meu = df[df["vendedor"] == nome]
    r = resumo_categorias(meu)
    st.markdown(f"### Bom dia, {nome.split()[0]}. Hoje você tem "
                f"**{r['Agir']}** deals para agir, **{r['Engajar']}** para engajar e **{r['Decidir']}** para decidir.")

    agir = meu[meu["categoria"] == "Agir"]
    st.subheader("Para agir hoje", anchor=False)
    if agir.empty:
        st.write("Nenhum deal em Engaging dentro da janela. Veja *Para engajar* e *Para decidir*.")
    else:
        quantos = _quantos(len(agir), minimo=3, padrao=5, key="n_agir")
        for i, (_, d) in enumerate(agir.head(quantos).iterrows(), start=1):
            cartao_deal(i, d)

    engajar = meu[meu["categoria"] == "Engajar"]
    st.subheader("Para engajar", anchor=False)
    st.caption("Prospecting não tem data: o score usa só encaixe e valor — sem sinal de tempo.")
    if engajar.empty:
        st.write("Nenhum deal em Prospecting.")
    else:
        for i, (_, d) in enumerate(engajar.head(3).iterrows(), start=1):
            cartao_deal(i, d)
        if len(engajar) > 3:
            st.caption(f"+ {len(engajar) - 3} na tabela completa abaixo.")

    decidir = meu[meu["categoria"] == "Decidir"]
    st.subheader(f"Para decidir — {len(decidir)} deals além da parede", anchor=False)
    if decidir.empty:
        st.write("Nenhum deal além da parede.")
    else:
        st.caption(f"Nenhum deal do histórico fechou depois de {meta['parede']} dias em Engaging. "
                   "Não é esforço, é decisão. Ordenado por valor. A coluna *decisão* é só desta sessão — "
                   "não grava no CRM.")
        editavel = decidir[["opportunity_id", "produto", "conta", "idade_dias", "valor_produto", "frase_F1"]].copy()
        editavel["conta"] = editavel["conta"].fillna("—")
        editavel.insert(0, "decisão", pd.array([pd.NA] * len(editavel), dtype="string"))
        st.data_editor(
            editavel, hide_index=True, width="stretch", key=f"decisoes_{nome}",
            disabled=[c for c in editavel.columns if c != "decisão"],
            column_config={
                "decisão": st.column_config.SelectboxColumn("decisão", options=["Requalificar", "Descartar"]),
                "valor_produto": st.column_config.NumberColumn("valor (USD)", format="%d"),
                "idade_dias": st.column_config.NumberColumn("dias", format="%d"),
                "frase_F1": st.column_config.TextColumn("seu encaixe", width="large"),
            },
        )

    with st.expander(f"Tabela completa — {len(meu)} deals, todas as colunas"):
        tabela(meu, COLS_TABELA)


def tela_manager(df: pd.DataFrame, meta: dict, escopo: str) -> None:
    r = resumo_categorias(df)
    st.markdown(f"**{escopo}** — Agir {n(r['Agir'])} · Engajar {n(r['Engajar'])} · Decidir {n(r['Decidir'])}")

    st.subheader("Por vendedor", anchor=False)
    por_v = (
        df.groupby("vendedor")
        .agg(
            manager=("manager", "first"), regiao=("regiao", "first"),
            agir=("categoria", lambda s: (s == "Agir").sum()),
            engajar=("categoria", lambda s: (s == "Engajar").sum()),
            decidir=("categoria", lambda s: (s == "Decidir").sum()),
            sem_conta=("conta", lambda s: s.isna().sum()),
            valor_em_decidir=("valor_produto", lambda s: s[df.loc[s.index, "categoria"] == "Decidir"].sum()),
            melhor_score=("score", "max"),
        )
        .sort_values("decidir", ascending=False)
        .reset_index()
    )
    st.dataframe(
        por_v, hide_index=True, width="stretch",
        column_config={
            "sem_conta": st.column_config.NumberColumn("sem conta", format="%d"),
            "valor_em_decidir": st.column_config.NumberColumn("valor parado em Decidir (USD)", format="%d"),
            "melhor_score": st.column_config.NumberColumn("melhor score", format="%.0f"),
        },
    )

    st.subheader("Decidir — ordenado por valor", anchor=False)
    st.caption("Os maiores primeiro. Cada linha é um deal que o histórico diz que não vai fechar sozinho: "
               "requalificar ou descartar.")
    decidir = df[df["categoria"] == "Decidir"]
    tabela(decidir, ["vendedor", "produto", "conta", "idade_dias", "valor_produto", "confianca", "frase_F1"])

    st.subheader("Agir — topo da fila do time", anchor=False)
    agir = df[df["categoria"] == "Agir"]
    quantos = _quantos(len(agir), minimo=5, padrao=10, key="n_agir_time")
    for i, (_, d) in enumerate(agir.head(quantos).iterrows(), start=1):
        cartao_deal(i, d, mostrar_vendedor=True)

    with st.expander(f"Tabela completa — {len(df)} deals"):
        tabela(df, ["vendedor", "manager", "regiao"] + COLS_TABELA)


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


def main() -> None:
    scored, meta = carregar()
    teams = meta["teams"]

    st.title("Lead Scorer — fila de atenção")
    st.warning(AVISO)
    st.caption(f"Dados até **{meta['referencia']}** (última data do CRM; nada usa a data de hoje). "
               f"Calibrado em {n(meta['n_fechados'])} deals fechados, win rate {meta['win_rate']:.0%}. "
               f"Parede: {meta['parede']} dias em Engaging.")

    with st.sidebar:
        st.header("Filtros")
        regiao = st.selectbox("Região", [TODOS] + sorted(teams["regional_office"].unique()))
        t = teams if regiao == TODOS else teams[teams["regional_office"] == regiao]
        manager = st.selectbox("Manager", [TODOS] + sorted(t["manager"].unique()))
        t = t if manager == TODOS else t[t["manager"] == manager]
        vendedores_escopo = sorted(t["sales_agent"])
        produtos = st.multiselect("Produto", sorted(scored["produto"].unique()), default=[],
                                  placeholder="Todos os produtos")
        st.divider()
        st.markdown("**Como o score é feito**")
        w2, w1, w3 = meta["pesos"]
        st.markdown(
            f"- **F2 · atenção pela idade** (peso {w2}): onde a decisão está acontecendo. "
            f"Degraus: {meta['degraus']}\n"
            f"- **F1 · encaixe vendedor × produto** (peso {w1}): seu histórico nesse produto, suavizado — "
            "contexto, não motor\n"
            f"- **F3 · valor em jogo** (peso {w3}): preço de tabela do produto, em log\n\n"
            "Prospecting usa só F1 e F3. Acima da parede não há score: há decisão."
        )
        st.caption("Lógica completa em process-log/04-logica-do-score.md")

    escopo_df = scored[scored["vendedor"].isin(vendedores_escopo)]
    if produtos:
        escopo_df = escopo_df[escopo_df["produto"].isin(produtos)]
    escopo = "Pipeline inteiro" if regiao == TODOS and manager == TODOS else (
        f"{manager}" if manager != TODOS else f"Região {regiao}")
    if produtos:
        escopo += " · " + ", ".join(produtos)

    # O achado principal fica na primeira tela, para todo mundo
    faixa_pipeline(escopo_df, meta, escopo)

    aba_v, aba_m = st.tabs(["Minha segunda-feira", "Visão do manager"])
    with aba_v:
        vendedores_com_deal = sorted(set(vendedores_escopo) & set(scored["vendedor"]))
        tela_vendedor(escopo_df, meta, vendedores_com_deal)
    with aba_m:
        vend_sel = st.multiselect("Vendedores", vendedores_escopo, default=[], placeholder="Todos do escopo")
        df_m = escopo_df if not vend_sel else escopo_df[escopo_df["vendedor"].isin(vend_sel)]
        tela_manager(df_m, meta, escopo if not vend_sel else ", ".join(vend_sel))


main()
