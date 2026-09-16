"""Carrega os 4 CSVs do CRM e aplica as correções decididas na auditoria.

Correções (process-log/02-auditoria-dados.md):
- `GTXPro` -> `GTX Pro` no pipeline (1.480 linhas que o join perderia).
- `technolgy` -> `technology` em accounts.sector (12 contas).

Regra de leakage: deal aberto nunca carrega `close_value` nem `close_date` —
`split_pipeline` descarta as duas colunas antes de qualquer scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

OPEN_STAGES = ("Prospecting", "Engaging")
CLOSED_STAGES = ("Won", "Lost")
LEAK_COLUMNS = ("close_value", "close_date")

PRODUCT_FIXES = {"GTXPro": "GTX Pro"}
SECTOR_FIXES = {"technolgy": "technology"}


@dataclass
class CRMData:
    accounts: pd.DataFrame
    products: pd.DataFrame
    teams: pd.DataFrame
    pipeline: pd.DataFrame
    fixes: dict[str, int] = field(default_factory=dict)


def load_crm(data_dir: Path = DATA_DIR) -> CRMData:
    """Lê os CSVs e devolve os dados já corrigidos."""
    data_dir = Path(data_dir)
    accounts = pd.read_csv(data_dir / "accounts.csv")
    products = pd.read_csv(data_dir / "products.csv")
    teams = pd.read_csv(data_dir / "sales_teams.csv")
    pipeline = pd.read_csv(data_dir / "sales_pipeline.csv", parse_dates=["engage_date", "close_date"])
    return apply_fixes(accounts, products, teams, pipeline)


def apply_fixes(
    accounts: pd.DataFrame, products: pd.DataFrame, teams: pd.DataFrame, pipeline: pd.DataFrame
) -> CRMData:
    """Aplica as correções de texto e valida que o join produto não perde linha."""
    accounts, pipeline = accounts.copy(), pipeline.copy()

    n_prod = int(pipeline["product"].isin(PRODUCT_FIXES).sum())
    pipeline["product"] = pipeline["product"].replace(PRODUCT_FIXES)

    n_sec = int(accounts["sector"].isin(SECTOR_FIXES).sum())
    accounts["sector"] = accounts["sector"].replace(SECTOR_FIXES)

    orphans = set(pipeline["product"]) - set(products["product"])
    if orphans:
        raise ValueError(f"Produtos do pipeline sem cadastro em products.csv: {sorted(orphans)}")

    fixes = {"GTXPro -> GTX Pro": n_prod, "technolgy -> technology": n_sec}
    return CRMData(accounts=accounts, products=products, teams=teams, pipeline=pipeline, fixes=fixes)


def split_pipeline(pipeline: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa histórico (Won/Lost) de abertos (Prospecting/Engaging).

    Os abertos saem SEM `close_value` e `close_date`: é a garantia estrutural
    de que essas colunas nunca viram feature.
    """
    closed = pipeline[pipeline["deal_stage"].isin(CLOSED_STAGES)].copy()
    open_deals = (
        pipeline[pipeline["deal_stage"].isin(OPEN_STAGES)]
        .drop(columns=[c for c in LEAK_COLUMNS if c in pipeline.columns])
        .copy()
    )
    return closed, open_deals
