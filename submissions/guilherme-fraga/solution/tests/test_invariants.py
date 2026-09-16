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


def test_f2_degraus_sao_propriedades_nao_numeros_decorados(calib):
    z = calib.zones.set_index("zona")
    assert z["f2"]["0–14"] == 100  # referência: a zona 0–14 é a escala
    assert ((z["f2"] >= 0) & (z["f2"] <= 100)).all()
    assert z["f2_curva"]["91–parede"] < 100  # a última zona não satura por construção (revisão B1)
    assert z["f2_curva"]["61–90"] > z["f2_curva"]["15–60"]  # segunda onda existe nos dados
    assert z["f2"]["15–60"] == max(z["f2_curva"]["15–60"], ScoringConfig().vale_minimo)  # piso de produto
    assert calib.wall_days == 138
    assert calib.cohort_start == pd.Timestamp("2017-03-01") and calib.notes["n_censurados"] > 1000


def test_censura_derruba_a_ultima_faixa(crm):
    """Sem os abertos no conjunto de risco, 'vivos' na última faixa == 'decididos' e o degrau vai a 100."""
    closed, open_deals = split_pipeline(crm.pipeline)
    sem = calibrate(closed, crm.products).zones.set_index("zona")["f2_curva"]
    com = calibrate(closed, crm.products, open_deals=open_deals).zones.set_index("zona")["f2_curva"]
    assert sem["91–parede"] == 100 and com["91–parede"] < 60
    assert sem["0–14"] == com["0–14"] == 100


def _pipeline_sintetico(durations: np.ndarray, seed: int = 0) -> pd.DataFrame:
    """Deals engajados ao longo de 400 dias; quem fecharia depois da referência fica aberto (censurado)."""
    rng = np.random.default_rng(seed)
    n = len(durations)
    engage = pd.Timestamp("2017-01-01") + pd.to_timedelta(rng.integers(0, 400, n), "D")
    close = engage + pd.to_timedelta(durations, "D")
    ref = pd.Timestamp("2018-02-04")  # 400 dias depois do início
    closed = close <= ref
    stage = np.where(closed, np.where(rng.random(n) < 0.6, "Won", "Lost"), "Engaging")
    return pd.DataFrame({
        "opportunity_id": [f"S{i}" for i in range(n)], "sales_agent": "X", "product": "GTX Basic",
        "account": None, "deal_stage": stage, "engage_date": engage,
        "close_date": pd.Series(close).where(closed, pd.NaT), "close_value": 0.0,
    })


def test_hazard_constante_da_curva_plana(crm):
    """Durações geométricas = hazard constante: todas as zonas têm que sair na mesma altura.

    (Durações *uniformes* não dão curva plana num hazard: quem chega vivo ao fim fecha com
    certeza, o hazard sobe por definição. O caso plano de um hazard é o geométrico.)"""
    rng = np.random.default_rng(1)
    dur = rng.geometric(p=0.02, size=40_000)  # 2% ao dia, média 50 dias
    pipe = _pipeline_sintetico(dur)
    closed, open_deals = split_pipeline(pipe)
    c = calibrate(closed, crm.products, ScoringConfig(vale_minimo=0), open_deals=open_deals)
    z = c.zones.set_index("zona")["f2_curva"]
    assert z["0–14"] == 100
    assert (z.drop("0–14") >= 85).all(), z.to_dict()  # plana dentro do ruído
    assert (c.curve["por_dia"].between(0.016, 0.024)).all(), c.curve[["faixa", "por_dia"]].to_dict("records")


def test_f2_override_so_quando_pedido(crm):
    closed, open_deals = split_pipeline(crm.pipeline)
    padrao = calibrate(closed, crm.products, open_deals=open_deals).zones.set_index("zona")["f2"]
    assert padrao["15–60"] == 35
    forcado = calibrate(closed, crm.products, ScoringConfig(f2_overrides=(("15–60", 50),)), open_deals=open_deals).zones.set_index("zona")["f2"]
    assert forcado["15–60"] == 50 and forcado["61–90"] == padrao["61–90"]
    sem_piso = calibrate(closed, crm.products, ScoringConfig(vale_minimo=0), open_deals=open_deals).zones.set_index("zona")["f2"]
    assert sem_piso["15–60"] < 35
    with pytest.raises(ValueError):
        calibrate(closed, crm.products, ScoringConfig(f2_overrides=(("nada", 1),)), open_deals=open_deals)


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


def test_base_do_historico(scored):
    n = scored["n_celula"]
    assert (scored.loc[n >= 50, "base_historico"] == "ampla").all()
    assert (scored.loc[(n >= 20) & (n < 50), "base_historico"] == "média").all()
    assert (scored.loc[n < 20, "base_historico"] == "pequena").all()
    assert "confianca" not in scored.columns  # renomeado (revisão I2): mede amostra do F1, não confiança no score


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


# ---------------------------------------------------------------------------
# Casos de borda (revisão externa D1)
# ---------------------------------------------------------------------------


def _linha(**kw) -> pd.DataFrame:
    base = dict(opportunity_id="X1", sales_agent="Moses Frase", product="GTX Basic", account=None,
                deal_stage="Engaging", engage_date=pd.NaT)
    base.update(kw)
    return pd.DataFrame([base])


def test_engaging_sem_engage_date_vai_para_engajar(crm, calib):
    from lead_scorer import score_open_deals
    out = score_open_deals(_linha(), calib, crm.teams)
    assert out["categoria"].iloc[0] == "Engajar" and pd.isna(out["F2"].iloc[0])
    assert "Engaging sem data de engajamento" in out["frase_F2"].iloc[0]
    assert out["score"].notna().all() and out["marcadores"].isna().all()


def test_engage_date_depois_da_referencia_levanta_erro(crm, calib):
    from lead_scorer import score_open_deals
    with pytest.raises(ValueError, match="Idade negativa"):
        score_open_deals(_linha(engage_date=pd.Timestamp("2018-03-01")), calib, crm.teams)
