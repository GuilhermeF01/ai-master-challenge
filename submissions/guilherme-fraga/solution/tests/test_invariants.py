"""Invariantes do loader e do scoring (process-log/04-logica-do-score.md)."""

import numpy as np
import pandas as pd
import pytest

from lead_scorer import ScoringConfig, calibrate, split_pipeline
from lead_scorer.scoring import _shrink, factor_fit

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_correcoes_no_load(crm):
    assert crm.fixes == {"GTXPro -> GTX Pro": 1480, "technolgy -> technology": 12}
    assert "GTXPro" not in set(crm.pipeline["product"])
    assert "technolgy" not in set(crm.accounts["sector"])
    assert set(crm.pipeline["product"]) <= set(crm.products["product"])  # 0 órfãos


def test_split(crm):
    closed, open_deals = split_pipeline(crm.pipeline)
    assert len(closed) == 6711 and len(open_deals) == 2089
    assert set(open_deals["deal_stage"]) == {"Prospecting", "Engaging"}


# ---------------------------------------------------------------------------
# Calibração
# ---------------------------------------------------------------------------


def test_pesos_somam_100():
    assert ScoringConfig().w_f1 + ScoringConfig().w_f2 + ScoringConfig().w_f3 == 100
    with pytest.raises(ValueError):
        ScoringConfig(w_f1=50, w_f2=50, w_f3=50)


def test_f2_e_um_u(calib):
    z = calib.zones.set_index("zona")["f2"]
    assert z["0–14"] == 100 and z["91–parede"] == 100
    assert z["61–90"] > z["15–60"]
    # a curva dá 20 no vale; o piso de produto sobe para 35 (05-backtest)
    assert calib.zones.set_index("zona")["f2_curva"]["15–60"] == 20 and z["15–60"] == 35
    assert min(z["0–14"], z["91–parede"]) > z["61–90"]
    assert calib.wall_days == 138


def test_f2_override_so_quando_pedido(crm):
    closed, _ = split_pipeline(crm.pipeline)
    padrao = calibrate(closed, crm.products).zones.set_index("zona")["f2"]
    assert padrao["15–60"] == 35
    forcado = calibrate(closed, crm.products, ScoringConfig(f2_overrides=(("15–60", 50),))).zones.set_index("zona")["f2"]
    assert forcado["15–60"] == 50 and forcado["61–90"] == padrao["61–90"]
    sem_piso = calibrate(closed, crm.products, ScoringConfig(vale_minimo=0)).zones.set_index("zona")["f2"]
    assert sem_piso["15–60"] == 20
    with pytest.raises(ValueError):
        calibrate(closed, crm.products, ScoringConfig(f2_overrides=(("nada", 1),)))


def test_celula_pequena_nao_manda():
    """Peso da célula = n / (n + K2): 17% com 10 deals, 38% com 30, 67% com 100."""
    k2 = ScoringConfig().k2
    assert 10 / (10 + k2) < 0.20
    assert abs(30 / (30 + k2) - 0.375) < 0.01
    # Exemplo do 04: 2 de 14 com vendedor a 60,0% cai em 50,5%, não em 14%
    g = 0.632
    vend = _shrink(105, 175, g, 50)
    assert abs(_shrink(2, 14, vend, k2) - 0.505) < 0.005


def test_f1_exemplos_do_04(calib):
    f1, _, n = factor_fit("Niesha Huffines", "GTX Pro", calib)
    assert n == 14 and round(f1) == 8
    f1, _, n = factor_fit("Moses Frase", "GTX Basic", calib)
    assert n == 59 and round(f1) == 83
    f1, frase, n = factor_fit("Hayden Neloms", "GTX Basic", calib)  # sem histórico no produto
    assert n == 0 and "ainda não fechou nenhum GTX Basic" in frase


def test_f3_log(calib):
    f3 = calib.products["f3"]
    assert f3["MG Special"] == 0 and f3["GTK 500"] == 100 and f3["GTX Pro"] == 72


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------


def test_todos_os_abertos_pontuados(scored):
    assert len(scored) == 2089
    assert scored["opportunity_id"].is_unique
    assert scored["categoria"].value_counts().to_dict() == {"Decidir": 1291, "Engajar": 500, "Agir": 298}


def test_fatores_e_score_em_0_100(scored):
    for col in ["F1", "F2", "F3", "score"]:
        v = scored[col].dropna()
        assert ((v >= 0) & (v <= 100)).all(), col


def test_regras_de_categoria(scored):
    eng, prosp = scored["stage"] == "Engaging", scored["stage"] == "Prospecting"
    assert (scored.loc[prosp, "categoria"] == "Engajar").all()
    assert (scored.loc[eng & (scored["idade_dias"] > 138), "categoria"] == "Decidir").all()
    assert (scored.loc[eng & (scored["idade_dias"] <= 138), "categoria"] == "Agir").all()
    assert scored.loc[scored["categoria"] == "Decidir", "score"].isna().all()
    assert scored.loc[scored["categoria"] != "Decidir", "score"].notna().all()


def test_prospecting_sem_f2_e_renormalizado(scored):
    p = scored[scored["categoria"] == "Engajar"]
    assert p["F2"].isna().all()
    assert p["frase_F2"].str.contains("não há sinal de tempo").all()
    esperado = (20 * p["F1"] + 25 * p["F3"]) / 45
    assert np.allclose(p["score"], esperado, atol=0.1)  # F1 e score arredondados a 1 casa


def test_engaging_usa_os_tres_pesos(scored):
    a = scored[scored["categoria"] == "Agir"]
    esperado = (55 * a["F2"] + 20 * a["F1"] + 25 * a["F3"]) / 100
    assert np.allclose(a["score"], esperado, atol=0.1)


def test_ordem(scored):
    assert scored["ordem_categoria"].is_monotonic_increasing
    for cat in ["Agir", "Engajar"]:
        s = scored.loc[scored["categoria"] == cat, "score"]
        assert s.is_monotonic_decreasing, cat
    d = scored[scored["categoria"] == "Decidir"]
    assert d["valor_produto"].is_monotonic_decreasing
    # dentro do mesmo valor, mais velho primeiro
    assert d.groupby("valor_produto")["idade_dias"].apply(lambda s: s.is_monotonic_decreasing).all()


def test_empate_no_score_janela_critica_primeiro(scored):
    a = scored[scored["categoria"] == "Agir"].reset_index(drop=True)
    critica = a["marcadores"].fillna("").str.contains("janela crítica")
    for score, grupo in a.groupby("score"):
        flags = critica.loc[grupo.index].tolist()
        assert flags == sorted(flags, reverse=True), f"score {score}: janela crítica deveria vir antes"
    # o caso concreto: Boris Faz tem dois GTX Pro empatados, o de 12 dias vem antes do de 117
    boris = a[(a["vendedor"] == "Boris Faz") & (a["produto"] == "GTX Pro")]
    assert boris["score"].nunique() == 1 and boris["idade_dias"].tolist()[:2] == [12, 117]


def test_confianca(scored):
    n = scored["n_celula"]
    assert (scored.loc[n >= 50, "confianca"] == "Alta").all()
    assert (scored.loc[(n >= 20) & (n < 50), "confianca"] == "Média").all()
    assert (scored.loc[n < 20, "confianca"] == "Baixa").all()


def test_marcadores(scored):
    a = scored[scored["categoria"] == "Agir"]
    assert (a.loc[a["idade_dias"] <= 14, "marcadores"] == "janela crítica").all()
    assert (a.loc[a["idade_dias"] >= 91, "marcadores"] == "última janela").all()
    assert a.loc[(a["idade_dias"] > 14) & (a["idade_dias"] < 91), "marcadores"].isna().all()
    assert scored.loc[scored["categoria"] != "Agir", "marcadores"].isna().all()


def test_toda_linha_tem_tres_frases(scored):
    for col in ["frase_F1", "frase_F2", "frase_F3"]:
        assert scored[col].str.len().gt(20).all(), col


def test_funciona_sem_conta(scored):
    sem_conta = scored["conta"].isna()
    assert sem_conta.sum() == 1425
    assert scored.loc[sem_conta & (scored["categoria"] != "Decidir"), "score"].notna().all()
