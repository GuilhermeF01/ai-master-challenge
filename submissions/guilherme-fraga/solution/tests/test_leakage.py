"""close_value e close_date nunca entram como feature de deal aberto.

Os três testes prometidos em process-log/04-logica-do-score.md, mais a prova de
que nada usa a data de hoje.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from conftest import run_scoring
from lead_scorer import calibrate, score_open_deals, split_pipeline
from lead_scorer.loader import LEAK_COLUMNS, OPEN_STAGES

SRC = Path(__file__).resolve().parents[1] / "src"


def test_permutar_close_columns_dos_abertos_nao_muda_nada(crm, scored):
    """1. Preencher close_value/close_date nos abertos com lixo: saída idêntica."""
    rng = np.random.default_rng(42)
    p = crm.pipeline.copy()
    is_open = p["deal_stage"].isin(OPEN_STAGES)
    n = int(is_open.sum())
    p.loc[is_open, "close_value"] = rng.integers(1, 30_000, size=n).astype(float)
    p.loc[is_open, "close_date"] = pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 400, size=n), "D")

    assert_frame_equal(run_scoring(crm, p), scored)


def test_scorer_nunca_recebe_close_columns(crm, calib):
    """2. O loader descarta as colunas e o scorer recusa se elas chegarem."""
    _, open_deals = split_pipeline(crm.pipeline)
    assert not set(LEAK_COLUMNS) & set(open_deals.columns)

    with_leak = open_deals.copy()
    with_leak["close_value"] = 0.0
    with pytest.raises(ValueError, match="close_value"):
        score_open_deals(with_leak, calib, crm.teams, crm.accounts)


def test_embaralhar_close_value_dos_fechados_nao_muda_nada(crm, scored):
    """3. close_value dos fechados também não vaza pela calibração."""
    rng = np.random.default_rng(7)
    p = crm.pipeline.copy()
    is_closed = ~p["deal_stage"].isin(OPEN_STAGES)
    vals = p.loc[is_closed, "close_value"].to_numpy()
    p.loc[is_closed, "close_value"] = rng.permutation(vals)

    assert_frame_equal(run_scoring(crm, p), scored)


def test_data_de_referencia_vem_dos_dados_nao_de_hoje(scored):
    assert scored.attrs["reference_date"] == "2017-12-31"
    src = "\n".join(f.read_text(encoding="utf-8") for f in SRC.rglob("*.py"))
    assert not re.search(r"\b(today|now|utcnow)\s*\(", src), "código de scoring não pode usar a data de hoje"
