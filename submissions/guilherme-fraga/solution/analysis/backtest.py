"""Backtest da fila: finge que uma data T é hoje e vê se o topo da fila achou onde a decisão estava.

Para cada corte semanal T (abril a 17/12 — a janela de 14 dias precisa caber antes de 31/12):
  1. calibra o score SÓ com o que fechou antes de T (os abertos em T entram na
     curva do F2 como censurados, sem olhar o futuro);
  2. população = TODOS os deals em Engaging em T: engajados até T e que fecharam
     depois de T OU nunca fecharam até 31/12 (revisão externa B2 — antes só
     entrava quem depois fechou, e isso escondia os que a fila mandou agir e
     nunca se decidiram);
  3. aplica o score com reference_date = T (mesmo motor do app, mesma ordem);
  4. métrica: dos top 20% de "Agir", quantos tiveram DESFECHO (ganho ou perda)
     até T + 14 dias. Quem nunca fechou conta zero.
  Baselines (B3): "mais novo primeiro" (engage_date desc — o que o vendedor faz
  no CRM sem ferramenta), "ordenar por valor", "F2 sozinho", e a média do grupo.
  Resumo por mediana e amplitude nos cortes, não por três datas à mão (I1).

A métrica de 14 dias mede tempo. F1 (encaixe) e F3 (valor) não são sinais de
tempo e não conseguem movê-la; a grade de pesos abaixo existe para deixar isso
visível, não para escolher peso.

Rodar (a partir de solution/): python analysis/backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_scorer import ScoringConfig, calibrate, load_crm, score_open_deals  # noqa: E402
from lead_scorer.loader import LEAK_COLUMNS  # noqa: E402

FIM_DOS_DADOS = pd.Timestamp("2017-12-31")
JANELA_DIAS = 14
TOPO = 0.20
CORTES = list(pd.date_range("2017-04-03", FIM_DOS_DADOS - pd.Timedelta(days=JANELA_DIAS), freq="7D"))
CORTES_ANTIGOS = [pd.Timestamp("2017-07-01"), pd.Timestamp("2017-08-15"), pd.Timestamp("2017-10-01")]

ANTIGA = dict(w_f2=40, w_f1=35, w_f3=25, vale_minimo=0)  # 04 v1 (vale = o que a curva der)
ATUAL = dict()  # default do motor


# ---------------------------------------------------------------------------
# Conjuntos em T
# ---------------------------------------------------------------------------


def conjuntos(pipeline: pd.DataFrame, T: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """(fechados antes de T, todos os deals em Engaging em T, desfecho até T+14)."""
    fechados = pipeline[pipeline["deal_stage"].isin(["Won", "Lost"])]
    calib_set = fechados[fechados["close_date"] < T]
    em_engaging = pipeline[
        (pipeline["engage_date"] <= T)
        & ((pipeline["close_date"] > T) | (pipeline["deal_stage"] == "Engaging"))
    ]
    decidiu = (em_engaging.set_index("opportunity_id")["close_date"] <= T + pd.Timedelta(days=JANELA_DIAS)).fillna(False)
    # É assim que o motor os vê em T: em Engaging, sem close_*
    populacao = em_engaging.assign(deal_stage="Engaging").drop(columns=list(LEAK_COLUMNS))
    return calib_set, populacao, decidiu


# ---------------------------------------------------------------------------
# Rankings e métrica
# ---------------------------------------------------------------------------


def taxa_topo(ordem: pd.Series, indicador: pd.Series, frac: float) -> float:
    """Taxa do indicador nos top X% de uma ordem de opportunity_id."""
    k = int(round(frac * len(ordem)))
    return float(indicador.loc[ordem.head(k)].mean()) if k else float("nan")


def taxa_topo_por_valor(df: pd.DataFrame, indicador: pd.Series, frac: float) -> float:
    """Top X% ordenando por preço do produto. Empates (só 7 preços) resolvidos de forma
    esperada: o grupo de preço que cruza a linha entra proporcionalmente."""
    k = frac * len(df)
    restante, acum = k, 0.0
    for _valor, grupo in sorted(df.groupby("valor_produto"), key=lambda kv: -kv[0]):
        if restante <= 0:
            break
        usa = min(len(grupo), restante)
        acum += usa * indicador.loc[grupo["opportunity_id"]].mean()
        restante -= usa
    return acum / k


def rodar(pipeline, products, teams, T, cfg: ScoringConfig) -> dict:
    calib_set, populacao, decidiu = conjuntos(pipeline, T)
    calib = calibrate(calib_set, products, cfg, open_deals=populacao, reference_date=T)
    fila = score_open_deals(populacao, calib, teams, reference_date=T)
    agir = fila[fila["categoria"] == "Agir"].reset_index(drop=True)
    if agir.empty:
        return {}
    nunca_fechou = set(pipeline.loc[pipeline["deal_stage"] == "Engaging", "opportunity_id"])
    mais_novo = agir.sort_values(["engage_date", "opportunity_id"], ascending=[False, True])["opportunity_id"]
    f2_so = agir.sort_values(["F2", "opportunity_id"], ascending=[False, True])["opportunity_id"]
    k = int(round(TOPO * len(agir)))
    return {
        "T": T, "n_calib": len(calib_set), "n_agir": len(agir),
        "n_decidir_em_T": int((fila["categoria"] == "Decidir").sum()),
        "n_nunca_fechou": int(agir["opportunity_id"].isin(nunca_fechou).sum()),
        "fila": taxa_topo(agir["opportunity_id"], decidiu, TOPO),
        "mais_novo": taxa_topo(mais_novo, decidiu, TOPO),
        "f2_so": taxa_topo(f2_so, decidiu, TOPO),
        "valor": taxa_topo_por_valor(agir, decidiu, TOPO),
        "grupo": float(decidiu.loc[agir["opportunity_id"]].mean()),
        "pct_topo_0_14": float(agir.head(k)["idade_dias"].le(14).mean()),
        "pct_topo_91_138": float(agir.head(k)["idade_dias"].ge(91).mean()),
    }


def resumo(rs: list[dict], chave: str) -> str:
    v = pd.Series([r[chave] for r in rs if r])
    return f"{v.median()*100:.1f}% ({v.min()*100:.0f}–{v.max()*100:.0f})"


def vitorias(rs: list[dict], a: str, b: str) -> str:
    rs = [r for r in rs if r]
    return f"{sum(r[a] > r[b] for r in rs)} / {len(rs)}"


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


def main() -> None:
    crm = load_crm()
    p, products, teams = crm.pipeline, crm.products, crm.teams

    print(f"## Cortes semanais: {len(CORTES)} (de {CORTES[0].date()} a {CORTES[-1].date()}), top {TOPO:.0%}, "
          f"desfecho em {JANELA_DIAS} dias\n")
    rs = [rodar(p, products, teams, T, ScoringConfig(**ATUAL)) for T in CORTES]
    rs = [r for r in rs if r]
    print("| Ordem | Mediana (min–máx) da taxa do top 20% | Vitórias da fila sobre esta ordem |")
    print("|---|---|---|")
    print(f"| **Fila (motor atual)** | **{resumo(rs, 'fila')}** | — |")
    print(f"| Mais novo primeiro (engage_date desc) | {resumo(rs, 'mais_novo')} | {vitorias(rs, 'fila', 'mais_novo')} |")
    print(f"| F2 sozinho | {resumo(rs, 'f2_so')} | {vitorias(rs, 'fila', 'f2_so')} |")
    print(f"| Ordenar por valor | {resumo(rs, 'valor')} | {vitorias(rs, 'fila', 'valor')} |")
    print(f"| Média do grupo (acaso) | {resumo(rs, 'grupo')} | {vitorias(rs, 'fila', 'grupo')} |")
    pop = pd.Series([r["n_agir"] for r in rs])
    nunca = pd.Series([r["n_nunca_fechou"] for r in rs])
    print(f"\nPopulação de Agir por corte: mediana {pop.median():.0f} (min {pop.min()}, máx {pop.max()}); "
          f"deles, nunca fecharam até 31/12: mediana {nunca.median():.0f} ({(nunca / pop).median():.0%}).")
    print(f"Composição do top 20% da fila: mediana de {pd.Series([r['pct_topo_0_14'] for r in rs]).median():.0%} em 0–14 dias "
          f"e {pd.Series([r['pct_topo_91_138'] for r in rs]).median():.0%} em 91–138.")

    print("\n### Por corte\n")
    print("| T | Agir em T | Nunca fecharam | Fila | Mais novo | F2 só | Valor | Grupo | Top 20% em 0–14 | em 91–138 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rs:
        print(f"| {r['T'].date()} | {r['n_agir']} | {r['n_nunca_fechou']} | {r['fila']*100:.0f}% | {r['mais_novo']*100:.0f}% | "
              f"{r['f2_so']*100:.0f}% | {r['valor']*100:.0f}% | {r['grupo']*100:.0f}% | {r['pct_topo_0_14']*100:.0f}% | "
              f"{r['pct_topo_91_138']*100:.0f}% |")

    print("\n## Configuração antiga (04 v1: 40/35/25, curva sem piso) vs atual, mesmos cortes\n")
    ra = [rodar(p, products, teams, T, ScoringConfig(**ANTIGA)) for T in CORTES]
    ra = [r for r in ra if r]
    print("| Configuração | Fila: mediana (min–máx) | Vitórias sobre mais novo primeiro |")
    print("|---|---|---|")
    print(f"| antiga 40 / 35 / 25, vale da curva | {resumo(ra, 'fila')} | {vitorias(ra, 'fila', 'mais_novo')} |")
    print(f"| atual 55 / 20 / 25, vale com piso 35 | {resumo(rs, 'fila')} | {vitorias(rs, 'fila', 'mais_novo')} |")
    print("\n(As duas rodam na curva com censura do B1; a curva antiga sem censura não existe mais no motor.)")

    print("\n## Os três cortes do 05 (v1), refeitos com a população completa\n")
    print("| T | Fila (05 v1, só quem fechou) | Fila agora | Mais novo | Valor | Grupo |")
    print("|---|---|---|---|---|---|")
    v1 = {pd.Timestamp("2017-07-01"): 46.7, pd.Timestamp("2017-08-15"): 37.6, pd.Timestamp("2017-10-01"): 40.3}
    for T in CORTES_ANTIGOS:
        r = rodar(p, products, teams, T, ScoringConfig(**ATUAL))
        print(f"| {T.date()} | {v1[T]:.1f}% | {r['fila']*100:.1f}% | {r['mais_novo']*100:.1f}% | {r['valor']*100:.1f}% | {r['grupo']*100:.1f}% |")

    print("\n## Grade de pesos na métrica de 14 dias (só para mostrar que F1 e F3 não a movem)\n")
    print("| Pesos F2 / F1 / F3 | Fila: mediana (min–máx) | Vitórias sobre mais novo |")
    print("|---|---|---|")
    for w2, w1, w3 in [(55, 20, 25), (40, 35, 25), (75, 0, 25), (100, 0, 0), (0, 50, 50)]:
        rg = [rodar(p, products, teams, T, ScoringConfig(w_f2=w2, w_f1=w1, w_f3=w3)) for T in CORTES]
        rg = [r for r in rg if r]
        print(f"| {w2} / {w1} / {w3} | {resumo(rg, 'fila')} | {vitorias(rg, 'fila', 'mais_novo')} |")


if __name__ == "__main__":
    main()
