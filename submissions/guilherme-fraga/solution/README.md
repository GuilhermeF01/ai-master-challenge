# Lead Scorer — setup e estrutura

Fila de atenção para o pipeline do CRM. O que o score é, por que, e o que ele não é: [`../README.md`](../README.md) e [`../process-log/04-logica-do-score.md`](../process-log/04-logica-do-score.md).

## Setup

```bash
pip install -r requirements.txt   # pandas, streamlit, pytest
streamlit run app.py              # http://localhost:8501
```

Sem API key, sem rede. Testado com Python 3.13, pandas 3.0, Streamlit 1.64.

| Comando | O que faz |
|---|---|
| `streamlit run app.py` | App: aba do vendedor ("Minha segunda-feira") e aba do manager. `?vendedor=Nome` na URL pré-seleciona. |
| `python src/score_pipeline.py` | Gera `output/pipeline_scored.csv` com os 2.089 deals abertos pontuados. |
| `pytest -q` | 36 testes: leakage (`close_value`/`close_date` nunca entram), invariantes, curva sintética, backtest, app. |
| `python analysis/backtest.py` | Backtest com 37 cortes semanais (~2 min). |
| `python analysis/test_hipoteses.py` | Reproduz o teste das hipóteses (só stdlib). |
| `python analysis/ml_check.py` | Check de ML (precisa de `scikit-learn`, que não é dependência do app). |

## Estrutura

```
solution/
├── app.py                      Streamlit: telas, filtros, cartões com as frases
├── src/
│   ├── score_pipeline.py       CLI: CSV → output/pipeline_scored.csv
│   └── lead_scorer/
│       ├── loader.py           4 CSVs, correções (GTXPro, technolgy), split fechados/abertos sem close_*
│       └── scoring.py          ScoringConfig, calibrate() (F1, curva do F2 com censura, F3), score_open_deals()
├── tests/
│   ├── test_leakage.py         3 provas de que close_value/close_date não entram + nada usa a data de hoje
│   ├── test_invariants.py      pesos, degraus como propriedades, curva sintética, categorias, ordem, casos de borda
│   ├── test_backtest.py        calibração nunca vê o futuro; população inclui quem nunca fechou
│   └── test_app.py             smoke test do app via streamlit.testing
├── analysis/                   scripts reproduzíveis das etapas do process-log (03, 03-D, 05)
├── data/                       os 4 CSVs do dataset (CC0) + metadata.csv
├── output/pipeline_scored.csv  saída do motor, 2.089 linhas
├── requirements.txt
└── pyproject.toml              só config do pytest (pythonpath = src)
```

Fluxo: `load_crm()` → `split_pipeline()` → `calibrate(fechados, produtos, open_deals=abertos)` → `score_open_deals(abertos, calib, times, contas)`. Toda calibração vem dos deals fechados; os abertos entram só como censura na curva do F2. A data de referência é a última data dos dados (2017-12-31).
