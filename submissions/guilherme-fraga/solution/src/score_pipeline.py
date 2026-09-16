"""Gera output/pipeline_scored.csv com todos os deals abertos pontuados.

Uso (a partir de solution/):
    python src/score_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from lead_scorer import calibrate, load_crm, score_open_deals, split_pipeline

SOLUTION_DIR = Path(__file__).resolve().parents[1]
OUTPUT = SOLUTION_DIR / "output" / "pipeline_scored.csv"


def main(output: Path = OUTPUT) -> pd.DataFrame:
    crm = load_crm()
    closed, open_deals = split_pipeline(crm.pipeline)
    calib = calibrate(closed, crm.products)
    scored = score_open_deals(open_deals, calib, crm.teams, crm.accounts)

    output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output, index=False)

    print(f"Correções no load: {crm.fixes}")
    print(f"Histórico: {calib.n_closed} fechados (win rate {calib.global_rate:.1%}), "
          f"parede = {calib.wall_days} dias, referência = {scored.attrs['reference_date']}")
    print("Degraus do F2:", dict(zip(calib.zones["zona"], calib.zones["f2"])))
    print(f"Abertos pontuados: {len(scored)}")
    print(scored["categoria"].value_counts().rename_axis("categoria").to_string())
    print(f"→ {output.relative_to(SOLUTION_DIR)}")
    return scored


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
