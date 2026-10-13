"""Shared pieces for the complaint classifier: labels, text prep, embeddings."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "ml" / "artifacts"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_ID = "bge-small+logreg"
MAX_CHARS = 800


def component_groups() -> dict[str, str]:
    """Raw NHTSA component prefix -> label. Same seed file dbt uses, so training and
    the warehouse can never disagree about what a label means."""
    with open(ROOT / "dbt" / "seeds" / "component_groups.csv", newline="") as f:
        return {r["component_prefix"]: r["component_group"] for r in csv.DictReader(f)}


def prep(text: str) -> str:
    return " ".join(str(text).split())[:MAX_CHARS]


_embedder = None


def embed(texts: list[str], batch_size: int = 64) -> np.ndarray:
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(MODEL_NAME)
    return np.vstack(list(_embedder.embed([prep(t) for t in texts], batch_size=batch_size)))
