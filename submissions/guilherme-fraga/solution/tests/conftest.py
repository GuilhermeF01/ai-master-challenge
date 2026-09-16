import pandas as pd
import pytest

from lead_scorer import CRMData, calibrate, load_crm, score_open_deals, split_pipeline


@pytest.fixture(scope="session")
def crm() -> CRMData:
    return load_crm()


def run_scoring(crm: CRMData, pipeline: pd.DataFrame | None = None) -> pd.DataFrame:
    """Pipeline completo: split → calibra → pontua. `pipeline` permite injetar variações."""
    closed, open_deals = split_pipeline(crm.pipeline if pipeline is None else pipeline)
    calib = calibrate(closed, crm.products, open_deals=open_deals)
    return score_open_deals(open_deals, calib, crm.teams, crm.accounts)


@pytest.fixture(scope="session")
def calib(crm):
    closed, open_deals = split_pipeline(crm.pipeline)
    return calibrate(closed, crm.products, open_deals=open_deals)


@pytest.fixture(scope="session")
def scored(crm) -> pd.DataFrame:
    return run_scoring(crm)
