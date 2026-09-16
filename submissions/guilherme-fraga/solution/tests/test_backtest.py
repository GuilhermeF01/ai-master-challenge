"""Propriedades do backtest (revisão externa D4): a calibração nunca vê o futuro
e a população de avaliação inclui quem nunca fechou."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))

import backtest  # noqa: E402
from lead_scorer.loader import LEAK_COLUMNS  # noqa: E402

T = pd.Timestamp("2017-08-14")


@pytest.fixture(scope="module")
def em_T(crm):
    return backtest.conjuntos(crm.pipeline, T)


def test_calibracao_nunca_ve_close_date_em_ou_depois_de_T(em_T):
    calib_set, _, _ = em_T
    assert (calib_set["close_date"] < T).all()
    assert set(calib_set["deal_stage"]) <= {"Won", "Lost"}


def test_populacao_inclui_quem_nunca_fechou_e_quem_fechou_depois(crm, em_T):
    _, populacao, decidiu = em_T
    nunca = set(crm.pipeline.loc[crm.pipeline["deal_stage"] == "Engaging", "opportunity_id"])
    depois = set(crm.pipeline.loc[crm.pipeline["close_date"] > T, "opportunity_id"])
    ids = set(populacao["opportunity_id"])
    assert ids & nunca and ids & depois
    assert (populacao["engage_date"] <= T).all()
    assert not set(LEAK_COLUMNS) & set(populacao.columns)  # o motor vê os deals como o app veria em T
    assert (populacao["deal_stage"] == "Engaging").all()
    # quem nunca fechou conta zero; quem fechou depois de T+14 também
    assert not decidiu.loc[list(ids & nunca)].any()
    tarde = crm.pipeline[crm.pipeline["close_date"] > T + pd.Timedelta(days=backtest.JANELA_DIAS)]["opportunity_id"]
    assert not decidiu.loc[decidiu.index.intersection(tarde)].any()


def test_cortes_deixam_a_janela_caber_antes_do_fim_dos_dados():
    assert backtest.CORTES[-1] + pd.Timedelta(days=backtest.JANELA_DIAS) <= backtest.FIM_DOS_DADOS
    assert len(backtest.CORTES) >= 30


def test_taxa_topo_por_valor_resolve_empate_de_forma_esperada():
    df = pd.DataFrame({"opportunity_id": list("abcdef"), "valor_produto": [10, 10, 10, 10, 1, 1]})
    ind = pd.Series([True, False, False, False, True, True], index=list("abcdef"))
    # top 50% = 3 deals, todos do grupo de valor 10 (taxa 1/4): esperado 0,25
    assert abs(backtest.taxa_topo_por_valor(df, ind, 0.5) - 0.25) < 1e-9
