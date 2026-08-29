"""
s06_evaluate.py
Evaluate the production classifier on the validation set.

Reports: macro F1, weighted F1, top-2 accuracy, per-class classification report.
Saves val predictions for downstream analysis.

Input:  data/modelling/val.csv
        models/sbert_val_embeddings.npy
        models/sbert_classifier_no_meta.joblib
Output: data/modelling/val_predictions.csv
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.metrics import classification_report, f1_score

# -----------------------------
# CONFIG
# -----------------------------
DATA_DIR = Path("data/modelling")
MODEL_DIR = Path("models")
LABEL_COL = "target"


def main():
    """Evaluate production model on val set."""
    # Load
    val_df = pd.read_csv(DATA_DIR / "val.csv")
    val_emb = np.load(MODEL_DIR / "sbert_val_embeddings.npy")
    clf = joblib.load(MODEL_DIR / "sbert_classifier_no_meta.joblib")
    y_val = val_df[LABEL_COL]
    label_names = list(clf.classes_)

    print(f"  Val set: {len(val_df)} articles")

    # Predict
    y_pred = clf.predict(val_emb)
    proba = clf.predict_proba(val_emb)

    # Metrics
    macro_f1 = f1_score(y_val, y_pred, average="macro")
    weighted_f1 = f1_score(y_val, y_pred, average="weighted")

    # Top-2
    top2_correct = []
    for i, true in enumerate(y_val):
        top2_idx = np.argsort(proba[i])[-2:][::-1]
        top2_classes = [clf.classes_[j] for j in top2_idx]
        top2_correct.append(true in top2_classes)
    top2_acc = np.mean(top2_correct)

    print(f"  Macro F1:    {macro_f1:.3f}")
    print(f"  Weighted F1: {weighted_f1:.3f}")
    print(f"  Top-2 acc:   {top2_acc:.1%}")
    print(f"\n{classification_report(y_val, y_pred)}")

    # Save predictions
    results = val_df[["title", "url"]].copy() if "title" in val_df.columns else val_df.iloc[:, :1].copy()
    results["true"] = y_val.values
    results["top1"] = y_pred
    results["top1_confidence"] = proba.max(axis=1)
    for i, row_proba in enumerate(proba):
        top2_idx = np.argsort(row_proba)[-2:][::-1]
        results.loc[results.index[i], "top2"] = clf.classes_[top2_idx[1]]
        results.loc[results.index[i], "top2_confidence"] = row_proba[top2_idx[1]]

    out_path = DATA_DIR / "val_predictions.csv"
    results.to_csv(out_path, index=False)
    print(f"  Saved predictions → {out_path}")
    print("  Done.")


if __name__ == "__main__":
    main()
