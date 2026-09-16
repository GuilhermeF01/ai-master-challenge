"""Backtest da fila: finge que uma data T é hoje e vê se o topo da fila acertou.

Para cada corte T:
  1. calibra o score SÓ com deals que fecharam antes de T;
  2. pega os deals que estavam em Engaging em T (engage_date <= T < close_date)
     e que depois fecharam — o desfecho é conhecido;
  3. aplica o score com reference_date = T (mesmo motor do app, mesma ordem);
  4. dos top 20% em "Agir", quantos ganharam — comparado com ordenar por valor
     e com a média do grupo.

Grade: vale do F2 (zona 15–60) em {20, 35, 50} × peso do F1 em {35, 20, 0}
(o que sai do F1 vai para o F2; F3 fixo em 25). Nada aqui muda o app.

Rodar (a partir de solution/): python analysis/backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_scorer import ScoringConfig, calibrate, load_crm, score_open_deals  # noqa: E402
from lead_scorer.loader import LEAK_COLUMNS  # noqa: E402

CORTES = [pd.Timestamp("2017-07-01"), pd.Timestamp("2017-08-15"), pd.Timestamp("2017-10-01")]
VALES = [20, 35, 50]
PESOS_F1 = [35, 20, 0]
TOPO = 0.20


def conjuntos(pipeline: pd.DataFrame, T: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """(fechados antes de T, abertos em Engaging em T que depois fecharam, desfecho)."""
    closed = pipeline[pipeline["deal_stage"].isin(["Won", "Lost"])]
    calib_set = closed[closed["close_date"] < T]
    eval_set = closed[(closed["engage_date"] <= T) & (closed["close_date"] > T)].copy()
    won = eval_set.set_index("opportunity_id")["deal_stage"].eq("Won")
    # No dia T esses deals estavam em Engaging: é assim que o motor os vê
    eval_open = eval_set.assign(deal_stage="Engaging").drop(columns=list(LEAK_COLUMNS))
    return calib_set, eval_open, won


def win_rate_topo_por_valor(df: pd.DataFrame, won: pd.Series, frac: float) -> float:
    """Top X% ordenando por preço do produto. Empates (só 7 preços) são resolvidos
    de forma esperada: o grupo que cruza a linha entra proporcionalmente."""
    k = frac * len(df)
    restante, acum_won = k, 0.0
    for _valor, grupo in sorted(df.groupby("valor_produto"), key=lambda kv: -kv[0]):
        if restante <= 0:
            break
        n = len(grupo)
        wr = won.loc[grupo["opportunity_id"]].mean()
        usa = min(n, restante)
        acum_won += usa * wr
        restante -= usa
    return acum_won / k


def rodar_config(pipeline, products, teams, T, cfg: ScoringConfig) -> dict:
    calib_set, eval_open, won = conjuntos(pipeline, T)
    calib = calibrate(calib_set, products, cfg)
    fila = score_open_deals(eval_open, calib, teams, reference_date=T)
    agir = fila[fila["categoria"] == "Agir"].reset_index(drop=True)
    decidir = fila[fila["categoria"] == "Decidir"]
    k = int(round(TOPO * len(agir)))
    k50 = int(round(0.50 * len(agir)))
    topo = agir.head(k)
    ganhou_topo = won.loc[topo["opportunity_id"]]
    return {
        "n_calib": len(calib_set), "n_eval": len(agir), "n_decidir_em_T": len(decidir),
        "wr_decidir_em_T": won.loc[decidir["opportunity_id"]].mean() if len(decidir) else float("nan"),
        "k": k,
        "wr_topo_score": ganhou_topo.mean(),
        "wr_topo_valor": win_rate_topo_por_valor(agir, won, TOPO),
        "wr_topo50_score": won.loc[agir.head(k50)["opportunity_id"]].mean(),
        "wr_topo50_valor": win_rate_topo_por_valor(agir, won, 0.50),
        "pct_topo50_vale": agir.head(k50)["idade_dias"].between(15, 60).mean(),
        "wr_grupo": won.loc[agir["opportunity_id"]].mean(),
        "pct_topo_janela_critica": topo["marcadores"].fillna("").str.contains("janela crítica").mean(),
        "pct_topo_ultima_janela": topo["marcadores"].fillna("").str.contains("última janela").mean(),
        "idade_mediana_topo": topo["idade_dias"].median(),
    }


def main() -> None:
    crm = load_crm()
    p, products, teams = crm.pipeline, crm.products, crm.teams

    print("## Cortes\n")
    print("| T (finge que é hoje) | Fechados antes de T (calibração) | Engaging em T que fecharam depois | Top 20% (k) | Win rate do grupo | Top 20% por valor |")
    print("|---|---|---|---|---|---|")
    base = {}
    for T in CORTES:
        r = rodar_config(p, products, teams, T, ScoringConfig())
        base[T] = r
        print(f"| {T.date()} | {r['n_calib']} | {r['n_eval']} | {r['k']} | {r['wr_grupo']*100:.1f}% | {r['wr_topo_valor']*100:.1f}% |")

    print("\n## Grade: win rate dos top 20% mandados a agir\n")
    cols = " | ".join(f"T={T.date()}" for T in CORTES)
    print(f"| Vale (15–60) | Pesos F2 / F1 / F3 | {cols} | Média | vs grupo | vs valor |")
    print("|---|---|" + "---|" * len(CORTES) + "---|---|---|")
    linhas = []
    for vale in VALES:
        for w1 in PESOS_F1:
            cfg = ScoringConfig(w_f1=w1, w_f2=40 + (35 - w1), w_f3=25, f2_overrides=(("15–60", vale),))
            rs = [rodar_config(p, products, teams, T, cfg) for T in CORTES]
            media = sum(r["wr_topo_score"] for r in rs) / len(rs)
            media_grupo = sum(r["wr_grupo"] for r in rs) / len(rs)
            media_valor = sum(r["wr_topo_valor"] for r in rs) / len(rs)
            celulas = " | ".join(f"{r['wr_topo_score']*100:.1f}%" for r in rs)
            marca = " ← atual" if (vale == 20 and w1 == 35) else ""
            print(f"| {vale} | {cfg.w_f2} / {cfg.w_f1} / {cfg.w_f3}{marca} | {celulas} | **{media*100:.1f}%** | "
                  f"{(media-media_grupo)*100:+.1f} pp | {(media-media_valor)*100:+.1f} pp |")
            linhas.append((vale, w1, rs))

    print("\n## Grade: win rate dos top 50% (alcança o vale)\n")
    print(f"| Vale (15–60) | Pesos F2 / F1 / F3 | {cols} | Média | vs grupo | vs valor | % do top 50% que está no vale (média) |")
    print("|---|---|" + "---|" * len(CORTES) + "---|---|---|---|")
    for vale, w1, rs in linhas:
        media = sum(r["wr_topo50_score"] for r in rs) / len(rs)
        media_grupo = sum(r["wr_grupo"] for r in rs) / len(rs)
        media_valor = sum(r["wr_topo50_valor"] for r in rs) / len(rs)
        no_vale = sum(r["pct_topo50_vale"] for r in rs) / len(rs)
        celulas = " | ".join(f"{r['wr_topo50_score']*100:.1f}%" for r in rs)
        marca = " ← atual" if (vale == 20 and w1 == 35) else ""
        print(f"| {vale} | {40 + (35 - w1)} / {w1} / 25{marca} | {celulas} | **{media*100:.1f}%** | "
              f"{(media-media_grupo)*100:+.1f} pp | {(media-media_valor)*100:+.1f} pp | {no_vale*100:.0f}% |")
    print("\nReferência top 50% por valor: " + " · ".join(f"T={T.date()}: {base[T]['wr_topo50_valor']*100:.1f}%" for T in CORTES))

    print("\n## O que está no topo (config atual, por corte)\n")
    print("| T | % do topo em janela crítica (≤14 d) | % do topo em última janela (91–138 d) | idade mediana do topo | Win rate topo | Win rate grupo |")
    print("|---|---|---|---|---|---|")
    for T in CORTES:
        r = base[T]
        print(f"| {T.date()} | {r['pct_topo_janela_critica']*100:.0f}% | {r['pct_topo_ultima_janela']*100:.0f}% | "
              f"{r['idade_mediana_topo']:.0f} | {r['wr_topo_score']*100:.1f}% | {r['wr_grupo']*100:.1f}% |")

    print("\n## Win rate por zona de idade EM T (o que o F2 está ordenando)\n")
    print("| T | 0–14 | 15–60 | 61–90 | 91–138 |")
    print("|---|---|---|---|---|")
    for T in CORTES:
        calib_set, eval_open, won = conjuntos(p, T)
        idade = (T - eval_open["engage_date"]).dt.days
        z = pd.cut(idade, [-1, 14, 60, 90, 138], labels=["0–14", "15–60", "61–90", "91–138"])
        w = won.loc[eval_open["opportunity_id"]].to_numpy()
        partes = []
        for nome in ["0–14", "15–60", "61–90", "91–138"]:
            m = (z == nome).to_numpy()
            partes.append(f"{w[m].mean()*100:.0f}% (n={m.sum()})" if m.sum() else "—")
        print(f"| {T.date()} | " + " | ".join(partes) + " |")


if __name__ == "__main__":
    main()


def dias_ate_a_perda(pipeline: pd.DataFrame) -> None:
    """Dos deals em cada zona em T que depois PERDERAM: quantos dias de T até a perda."""
    print("\n## Quantos dias o vendedor tem: dias de T até a perda, deals que perderam (mediana · p75)\n")
    print("| T | 0–14 em T | 15–60 em T | 61–90 em T |")
    print("|---|---|---|---|")
    for T in CORTES:
        _, eval_open, won = conjuntos(pipeline, T)
        ev = eval_open.assign(won=won.loc[eval_open["opportunity_id"]].to_numpy(),
                              idade=(T - eval_open["engage_date"]).dt.days)
        closed = pipeline.set_index("opportunity_id")["close_date"]
        ev["dias_ate_fechar"] = (pd.Series(closed.loc[ev["opportunity_id"]].to_numpy(), index=ev.index) - T).dt.days
        partes = []
        for lo, hi in [(0, 14), (15, 60), (61, 90)]:
            m = ev[(ev["idade"].between(lo, hi)) & (~ev["won"])]["dias_ate_fechar"]
            partes.append(f"{m.median():.0f} · {m.quantile(0.75):.0f} (n={len(m)})" if len(m) else "—")
        print(f"| {T.date()} | " + " | ".join(partes) + " |")


if __name__ == "__main__":
    dias_ate_a_perda(load_crm().pipeline)
