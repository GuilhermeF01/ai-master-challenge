"""Check rápido: um modelo faria melhor que a heurística?

Regressão logística nos deals fechados com split temporal (treina nos que fecharam
antes do corte, testa nos que fecharam depois). Reporta AUC.

Só análise — requer scikit-learn, que NÃO é dependência do app.
Rodar: python solution/analysis/ml_check.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

DATA = Path(__file__).resolve().parent.parent / "data"
K1, K2 = 50, 50
BANDS = [0, 8, 15, 31, 61, 91, 121, 10_000]  # 0–7, 8–14, 15–30, 31–60, 61–90, 91–120, 121+
PRICE_F3 = {"MG Special": 0, "GTX Basic": 37, "GTX Plus Basic": 48, "MG Advanced": 67,
            "GTX Pro": 72, "GTX Plus Pro": 74, "GTK 500": 100}


def f2_u(days: pd.Series) -> pd.Series:
    """Degraus de atenção em U (04-logica-do-score.md)."""
    return pd.cut(days, [-1, 14, 60, 90, 10_000], labels=[100, 20, 65, 100], ordered=False).astype(int)


def smoothed_f1(train: pd.DataFrame, apply_to: pd.DataFrame) -> pd.Series:
    """Célula vendedor×produto suavizada, calibrada só no treino."""
    g = train["won"].mean()
    v = train.groupby("sales_agent")["won"].agg(["sum", "count"])
    v_s = (v["sum"] + K1 * g) / (v["count"] + K1)
    c = train.groupby(["sales_agent", "product"])["won"].agg(["sum", "count"])
    vend = apply_to["sales_agent"].map(v_s).fillna(g)
    idx = pd.MultiIndex.from_frame(apply_to[["sales_agent", "product"]])
    c_sum = c["sum"].reindex(idx).fillna(0).to_numpy()
    c_n = c["count"].reindex(idx).fillna(0).to_numpy()
    cell = (c_sum + K2 * vend.to_numpy()) / (c_n + K2)
    return pd.Series(np.clip(50 + (cell - g) * 100 / 0.30, 0, 100), index=apply_to.index)


def main() -> None:
    p = pd.read_csv(DATA / "sales_pipeline.csv", parse_dates=["engage_date", "close_date"])
    p["product"] = p["product"].replace({"GTXPro": "GTX Pro"})
    closed = p[p["deal_stage"].isin(["Won", "Lost"])].copy()
    closed["won"] = (closed["deal_stage"] == "Won").astype(int)
    closed["days"] = (closed["close_date"] - closed["engage_date"]).dt.days
    closed["band"] = pd.cut(closed["days"], BANDS, right=False).astype(str)

    cut = closed["close_date"].quantile(0.70)
    train = closed[closed["close_date"] < cut]
    test = closed[closed["close_date"] >= cut]
    print(f"Corte temporal: close_date < {cut.date()} treina, ≥ testa.")
    print(f"Treino: {len(train)} deals (win rate {train['won'].mean()*100:.1f}%) · "
          f"Teste: {len(test)} deals (win rate {test['won'].mean()*100:.1f}%)\n")

    def design(cols, interaction=False):
        X = closed[cols].copy()
        if interaction:
            X["vp"] = closed["sales_agent"] + " × " + closed["product"]
        cat = [c for c in X.columns if c != "days"]  # tudo que não é idade numérica é categórico
        X = pd.get_dummies(X, columns=cat, dtype=float)
        if "days" in X.columns:
            X["days"] = X["days"] / 100.0
        return X

    specs = [
        ("LR vendedor + produto + idade (linear)", ["sales_agent", "product", "days"], False),
        ("LR vendedor + produto + idade (faixas)", ["sales_agent", "product", "band"], False),
        ("LR vendedor + produto (sem idade)", ["sales_agent", "product"], False),
        ("LR idade (faixas) só", ["band"], False),
        ("LR vendedor×produto + idade (faixas)", ["band"], True),
    ]
    rows = []
    for name, cols, inter in specs:
        X = design(cols, inter)
        m = LogisticRegression(max_iter=2000, C=1.0).fit(X.loc[train.index], train["won"])
        rows.append((name, roc_auc_score(train["won"], m.predict_proba(X.loc[train.index])[:, 1]),
                     roc_auc_score(test["won"], m.predict_proba(X.loc[test.index])[:, 1]), X.shape[1]))

    f1_test = smoothed_f1(train, test)
    f1_train = smoothed_f1(train, train)
    rows.append(("Heurística F1 só (célula suavizada, K1=K2=50)",
                 roc_auc_score(train["won"], f1_train), roc_auc_score(test["won"], f1_test), 1))
    score_test = 0.40 * f2_u(test["days"]) + 0.35 * f1_test + 0.25 * test["product"].map(PRICE_F3)
    score_train = 0.40 * f2_u(train["days"]) + 0.35 * f1_train + 0.25 * train["product"].map(PRICE_F3)
    rows.append(("Heurística score completo (F2 em U) — não é probabilidade",
                 roc_auc_score(train["won"], score_train), roc_auc_score(test["won"], score_test), 3))

    print("| Modelo | Features | AUC treino | AUC teste |")
    print("|---|---|---|---|")
    for name, a_tr, a_te, k in rows:
        print(f"| {name} | {k} | {a_tr:.3f} | {a_te:.3f} |")


if __name__ == "__main__":
    main()
