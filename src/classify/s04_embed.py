"""
s04_embed.py
Generate sentence transformer embeddings for train, val, or new articles.

Uses all-MiniLM-L6-v2 (frozen — no fine-tuning).
Saves embeddings as .npy files for downstream classification.

Input:  data/modelling/train.csv  OR  data/modelling/val.csv  OR new articles CSV
Output: models/sbert_train_embeddings.npy  OR  models/sbert_val_embeddings.npy
"""

import numpy as np
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer

# -----------------------------
# CONFIG
# -----------------------------
MODEL_NAME = "all-MiniLM-L6-v2"
DATA_DIR = Path("data/modelling")
MODEL_DIR = Path("models")
TEXT_COL = "text_clean"


def embed(texts, model_name=MODEL_NAME):
    """Encode a list of texts into sentence embeddings."""
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, show_progress_bar=True)
    return embeddings


def main():
    """Generate embeddings for train and val sets."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for split in ["train", "val"]:
        csv_path = DATA_DIR / f"{split}.csv"
        if not csv_path.exists():
            print(f"  Skipping {split} — {csv_path} not found")
            continue

        df = pd.read_csv(csv_path)
        texts = df[TEXT_COL].tolist()
        print(f"  Embedding {len(texts)} {split} articles...")

        embeddings = embed(texts)
        out_path = MODEL_DIR / f"sbert_{split}_embeddings.npy"
        np.save(out_path, embeddings)
        print(f"  Saved → {out_path} ({embeddings.shape})")

    print("  Done.")


if __name__ == "__main__":
    main()
