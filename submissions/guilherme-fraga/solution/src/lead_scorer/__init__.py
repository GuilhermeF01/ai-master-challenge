"""Lead Scorer — fila de atenção para o pipeline do CRM.

Lógica documentada em process-log/04-logica-do-score.md.
"""

from .loader import CRMData, load_crm, split_pipeline
from .scoring import Calibration, ScoringConfig, calibrate, score_open_deals

__all__ = [
    "CRMData",
    "Calibration",
    "ScoringConfig",
    "calibrate",
    "load_crm",
    "score_open_deals",
    "split_pipeline",
]
