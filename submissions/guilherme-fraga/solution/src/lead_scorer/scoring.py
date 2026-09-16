"""Scoring: três fatores, categorias de ação, confiança e frases.

Implementa process-log/04-logica-do-score.md. O score é FILA DE ATENÇÃO,
não probabilidade de fechar.

    score = (w_f2 * F2 + w_f1 * F1 + w_f3 * F3) / 100            # Engaging <= parede
    score = (w_f1 * F1 + w_f3 * F3) / (w_f1 + w_f3)              # Prospecting (sem F2)
    Decidir (Engaging > parede): sem score de fila

Toda calibração vem dos deals fechados (`calibrate`). Nada usa a data de hoje:
a data de referência é a última data que existe nos dados.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .loader import LEAK_COLUMNS

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringConfig:
    """Constantes aprovadas no 04. O backtest varia isso; o app usa o default."""

    k1: int = 50  # puxa a média do vendedor para a média geral
    k2: int = 50  # puxa a célula vendedor×produto para a média do vendedor
    w_f2: int = 40  # atenção pela idade
    w_f1: int = 35  # encaixe vendedor×produto
    w_f3: int = 25  # valor em jogo
    f1_scale_pp: float = 15.0  # ±15 pp em torno da média geral cobre 0–100
    conf_alta: int = 50  # n da célula para confiança Alta
    conf_media: int = 20  # n da célula para confiança Média
    # Zonas do U (cortes fixos; a parede vem dos dados)
    zone_edges: tuple[int, int, int] = (14, 60, 90)
    # Faixas finas usadas para medir "decididos por dia"
    fine_bands: tuple[tuple[int, int | None], ...] = (
        (0, 7), (8, 14), (15, 30), (31, 60), (61, 90), (91, 120), (121, None),
    )
    janela_critica_max: int = 14
    ultima_janela_min: int = 91

    def __post_init__(self) -> None:
        if self.w_f1 + self.w_f2 + self.w_f3 != 100:
            raise ValueError("Pesos precisam somar 100")


# ---------------------------------------------------------------------------
# Calibração (só com deals fechados)
# ---------------------------------------------------------------------------


@dataclass
class Calibration:
    config: ScoringConfig
    global_rate: float  # Won / (Won + Lost)
    last_close_date: pd.Timestamp
    wall_days: int  # maior duração em Engaging entre os fechados (138)
    vendor: pd.DataFrame  # index sales_agent: won, n, raw, suav
    cell: pd.DataFrame  # index (sales_agent, product): won, n, raw, suav
    curve: pd.DataFrame  # faixas finas: desfechos, vivos, por_dia
    zones: pd.DataFrame  # zonas do U: lo, hi, f2
    products: pd.DataFrame  # index product: sales_price, f3, rank (1 = mais caro)
    n_closed: int = 0
    n_won: int = 0
    notes: dict = field(default_factory=dict)

    # --- lookups -----------------------------------------------------------

    def vendor_row(self, agent: str) -> pd.Series | None:
        return self.vendor.loc[agent] if agent in self.vendor.index else None

    def cell_row(self, agent: str, product: str) -> pd.Series | None:
        key = (agent, product)
        return self.cell.loc[key] if key in self.cell.index else None

    def zone_for(self, age_days: int) -> pd.Series | None:
        hit = self.zones[(self.zones["lo"] <= age_days) & (age_days <= self.zones["hi"])]
        return hit.iloc[0] if len(hit) else None


def _shrink(won: float, n: float, prior: float, k: int) -> float:
    return (won + k * prior) / (n + k)


def calibrate(closed: pd.DataFrame, products: pd.DataFrame, config: ScoringConfig | None = None) -> Calibration:
    """Calcula tudo que o scoring precisa a partir do histórico (Won/Lost)."""
    cfg = config or ScoringConfig()
    closed = closed[closed["deal_stage"].isin(["Won", "Lost"])].copy()
    if closed.empty:
        raise ValueError("Sem deals fechados para calibrar")
    closed["won"] = (closed["deal_stage"] == "Won").astype(int)
    closed["days"] = (closed["close_date"] - closed["engage_date"]).dt.days

    g = float(closed["won"].mean())

    # F1: vendedor puxado para a média geral, célula puxada para o vendedor
    vendor = closed.groupby("sales_agent")["won"].agg(won="sum", n="count")
    vendor["raw"] = vendor["won"] / vendor["n"]
    vendor["suav"] = _shrink(vendor["won"], vendor["n"], g, cfg.k1)

    cell = closed.groupby(["sales_agent", "product"])["won"].agg(won="sum", n="count")
    cell["raw"] = cell["won"] / cell["n"]
    vend_prior = cell.index.get_level_values("sales_agent").map(vendor["suav"])
    cell["suav"] = _shrink(cell["won"], cell["n"], vend_prior.to_numpy(), cfg.k2)

    # F2: quanto do que ainda estava vivo foi decidido, por dia, em cada faixa
    wall = int(closed["days"].max())
    days = closed["days"].to_numpy()
    rows = []
    for lo, hi in cfg.fine_bands:
        hi_eff = wall if hi is None else hi
        if lo > wall:
            continue
        decided = int(((days >= lo) & (days <= hi_eff)).sum())
        alive = int((days >= lo).sum())
        length = hi_eff - lo + 1
        rows.append({"faixa": f"{lo}–{hi_eff}", "lo": lo, "hi": hi_eff, "desfechos": decided,
                     "vivos": alive, "por_dia": decided / alive / length if alive else 0.0})
    curve = pd.DataFrame(rows)

    e1, e2, e3 = cfg.zone_edges
    zone_defs = [("0–14", 0, e1), ("15–60", e1 + 1, e2), ("61–90", e2 + 1, e3), ("91–parede", e3 + 1, wall)]
    # Referência = taxa por dia da zona inteira 0–14 (2,79% nos dados originais)
    ref_decided = int(((days >= 0) & (days <= e1)).sum())
    ref = ref_decided / len(days) / (e1 + 1)
    zrows = []
    for name, lo, hi in zone_defs:
        inside = curve[(curve["lo"] >= lo) & (curve["hi"] <= hi)]
        # A zona recebe a atenção do seu trecho mais decisivo, relativa às duas primeiras semanas
        peak = float(inside["por_dia"].max()) if len(inside) else 0.0
        f2 = int(min(100, round(peak / ref * 100))) if ref > 0 else 0
        zrows.append({"zona": name, "lo": lo, "hi": hi, "por_dia_pico": peak, "f2": f2,
                      "desfechos": int(inside["desfechos"].sum()),
                      "pct_desfechos": float(inside["desfechos"].sum() / len(days))})
    zones = pd.DataFrame(zrows)

    # F3: preço em log, 0 = mais barato, 100 = mais caro
    prod = products.set_index("product")[["sales_price"]].copy()
    lo_p, hi_p = math.log(prod["sales_price"].min()), math.log(prod["sales_price"].max())
    prod["f3"] = ((np.log(prod["sales_price"]) - lo_p) / (hi_p - lo_p) * 100).round().astype(int)
    prod["rank"] = prod["sales_price"].rank(ascending=False, method="min").astype(int)

    return Calibration(
        config=cfg, global_rate=g, last_close_date=closed["close_date"].max(), wall_days=wall,
        vendor=vendor, cell=cell, curve=curve, zones=zones, products=prod,
        n_closed=int(len(closed)), n_won=int(closed["won"].sum()),
    )


# ---------------------------------------------------------------------------
# Fatores (número 0–100 + frase)
# ---------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{round(x * 100):d}%"


def _usd(x: float) -> str:
    return "USD " + f"{int(round(x)):,}".replace(",", ".")


def factor_fit(agent: str, product: str, calib: Calibration) -> tuple[float, str, int]:
    """F1 — encaixe vendedor×produto suavizado. Devolve (F1, frase, n da célula)."""
    cfg, g = calib.config, calib.global_rate
    v = calib.vendor_row(agent)
    c = calib.cell_row(agent, product)

    if v is None:
        f1 = 50.0
        return f1, f"Você ainda não tem deal fechado no histórico. O score usa a média geral ({_pct(g)}).", 0

    if c is None:
        suav = float(v["suav"])
        n_cell = 0
        frase = f"Você ainda não fechou nenhum {product}. O score usa a sua média geral ({_pct(v['raw'])})."
    else:
        suav, n_cell = float(c["suav"]), int(c["n"])
        won, raw = int(c["won"]), float(c["raw"])
        if n_cell < cfg.conf_media:
            frase = (f"Seu histórico em {product} é {won} de {n_cell} ({_pct(raw)}). Base pequena: "
                     f"o score usa {_pct(suav)} (puxado para a sua média de {_pct(v['raw'])}).")
        elif suav >= g:
            grau = "bem acima" if raw - g >= 0.10 else "acima"
            frase = f"Você fecha {product} em {won} de {n_cell} deals ({_pct(raw)}) — {grau} da média geral ({_pct(g)})."
        else:
            ref = (f"abaixo da sua média ({_pct(v['raw'])}) e da geral ({_pct(g)})"
                   if raw < v["raw"] else f"abaixo da média geral ({_pct(g)})")
            frase = f"Seu histórico em {product} é {won} de {n_cell} ({_pct(raw)}) — {ref}."

    f1 = float(np.clip(50 + (suav - g) * 100 / (2 * cfg.f1_scale_pp / 100), 0, 100))
    return f1, frase, n_cell


def factor_age(age_days: int | None, calib: Calibration) -> tuple[float | None, str, str]:
    """F2 — necessidade de atenção pela idade (U). Devolve (F2 ou None, frase, zona)."""
    if age_days is None:
        return None, "Sem data de engajamento: não há sinal de tempo. Score usa só encaixe e valor.", "prospecting"

    wall = calib.wall_days
    if age_days > wall:
        return None, (f"Há {age_days} dias em Engaging — nenhum deal fechou depois de {wall} dias. "
                      f"Não é esforço, é decisão: requalificar ou descartar."), "sem precedente"

    z = calib.zone_for(age_days)
    zones = calib.zones.set_index("zona")
    pct = lambda name: f"{round(zones.loc[name, 'pct_desfechos'] * 100):d}%"  # noqa: E731
    name = z["zona"]
    if name == "0–14":
        frase = (f"Há {age_days} dias em Engaging. Metade das perdas acontece até o dia 14 — "
                 f"é agora que o seu esforço evita a perda.")
    elif name == "15–60":
        frase = (f"Há {age_days} dias em Engaging. Zona de follow-up: só {pct(name)} dos desfechos acontecem "
                 f"entre os dias 15 e 60. Mantenha a cadência.")
    elif name == "61–90":
        frase = (f"Há {age_days} dias em Engaging. Segunda onda de decisões: {pct(name)} dos desfechos "
                 f"acontecem entre 61 e 90 dias.")
    else:
        frase = (f"Há {age_days} dias em Engaging. Última janela: 80% dos que fecham já fecharam aos 90 dias "
                 f"e nenhum passou de {wall}. Empurre para a decisão.")
    return float(z["f2"]), frase, name


def factor_value(product: str, calib: Calibration) -> tuple[float, str]:
    """F3 — valor em jogo (sales_price em log). Devolve (F3, frase)."""
    p = calib.products.loc[product]
    total, rank = len(calib.products), int(p["rank"])
    if rank == 1:
        pos = "o produto mais caro do catálogo"
    elif rank == total:
        pos = "o produto mais barato do catálogo"
    else:
        pos = f"{rank}º produto mais caro dos {total}"
    return float(p["f3"]), f"{product}: {_usd(p['sales_price'])} em jogo — {pos}."


# ---------------------------------------------------------------------------
# Score por deal
# ---------------------------------------------------------------------------

CATEGORIES = {"Agir": 1, "Engajar": 2, "Decidir": 3}


def score_open_deals(
    open_deals: pd.DataFrame,
    calib: Calibration,
    teams: pd.DataFrame,
    accounts: pd.DataFrame | None = None,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Pontua os deals abertos e devolve a fila ordenada.

    `open_deals` NÃO pode trazer close_value/close_date — o loader já descarta;
    aqui é a segunda trava.
    """
    leaked = [c for c in LEAK_COLUMNS if c in open_deals.columns]
    if leaked:
        raise ValueError(f"Deal aberto não pode carregar {leaked} — use split_pipeline()")

    cfg = calib.config
    if reference_date is None:
        reference_date = max(calib.last_close_date, open_deals["engage_date"].max())
    reference_date = pd.Timestamp(reference_date)

    team = teams.set_index("sales_agent")
    acc = accounts.set_index("account") if accounts is not None else None

    rows = []
    for d in open_deals.itertuples(index=False):
        engaging = d.deal_stage == "Engaging"
        age = int((reference_date - d.engage_date).days) if engaging and pd.notna(d.engage_date) else None

        f1, frase_f1, n_cell = factor_fit(d.sales_agent, d.product, calib)
        f2, frase_f2, zona = factor_age(age, calib)
        f3, frase_f3 = factor_value(d.product, calib)

        if engaging and age is not None and age > calib.wall_days:
            categoria, score = "Decidir", np.nan
        elif engaging:
            categoria = "Agir"
            score = (cfg.w_f2 * f2 + cfg.w_f1 * f1 + cfg.w_f3 * f3) / 100
        else:
            categoria = "Engajar"
            score = (cfg.w_f1 * f1 + cfg.w_f3 * f3) / (cfg.w_f1 + cfg.w_f3)

        marcadores = []
        if categoria == "Agir" and age <= cfg.janela_critica_max:
            marcadores.append("janela crítica")
        if categoria == "Agir" and age >= cfg.ultima_janela_min:
            marcadores.append("última janela")

        if n_cell >= cfg.conf_alta:
            conf = "Alta"
        elif n_cell >= cfg.conf_media:
            conf = "Média"
        else:
            conf = "Baixa"

        t = team.loc[d.sales_agent] if d.sales_agent in team.index else None
        conta = d.account if isinstance(d.account, str) and d.account else None
        a = acc.loc[conta] if (acc is not None and conta in acc.index) else None

        rows.append({
            "opportunity_id": d.opportunity_id,
            "vendedor": d.sales_agent,
            "manager": t["manager"] if t is not None else None,
            "regiao": t["regional_office"] if t is not None else None,
            "produto": d.product,
            "conta": conta,
            "setor": a["sector"] if a is not None else None,
            "stage": d.deal_stage,
            "engage_date": d.engage_date.date() if pd.notna(d.engage_date) else None,
            "idade_dias": age,
            "valor_produto": float(calib.products.loc[d.product, "sales_price"]),
            "categoria": categoria,
            "ordem_categoria": CATEGORIES[categoria],
            "score": round(score, 1) if pd.notna(score) else np.nan,
            "confianca": conf,
            "n_celula": n_cell,
            "F1": round(f1, 1),
            "F2": f2,
            "F3": f3,
            "frase_F1": frase_f1,
            "frase_F2": frase_f2,
            "frase_F3": frase_f3,
            "marcadores": "; ".join(marcadores) or None,
        })

    out = pd.DataFrame(rows)
    # Categoria manda na ordem; score desempata em Agir/Engajar; Decidir por valor, depois idade.
    # Empate no score: janela crítica primeiro — ali a perda é questão de dias.
    decidir = out["categoria"] == "Decidir"
    critica = out["marcadores"].fillna("").str.contains("janela crítica")
    out["_k2"] = np.where(decidir, -out["valor_produto"], -out["score"].fillna(-1))
    out["_k3"] = np.where(decidir, -out["idade_dias"].fillna(0), np.where(critica, 0, 1))
    out = (
        out.sort_values(["ordem_categoria", "_k2", "_k3", "opportunity_id"])
        .drop(columns=["_k2", "_k3"])
        .reset_index(drop=True)
    )
    out.attrs["reference_date"] = reference_date.date().isoformat()
    return out
