"""Train the complaint classifier once, from NHTSA's full current-period file.

Time-based split: train on complaints received before CUTOFF, test on complaints
received after it. That mirrors production, where the model only ever sees new
complaints, and it is stricter than a random split.

    python -m ml.train            # writes ml/artifacts/{classifier.joblib, offline_metrics.json}
"""
from __future__ import annotations

import datetime as dt
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report

from ml.common import ARTIFACTS, MODEL_ID, MODEL_NAME, component_groups, embed
from pipeline.ingest_nhtsa import download

CUTOFF = pd.Timestamp("2026-07-01")
TRAIN_PER_CLASS = 1000
TEST_PER_CLASS = 250
SEED = 7


def labeled_complaints() -> pd.DataFrame:
    rows = download(dt.date.today().year)
    rows["prefix"] = rows["component"].str.split(":").str[0].str.strip().str.upper()
    per = rows.groupby("odino").agg(
        n=("component", "size"), prefix=("prefix", "first"),
        received=("date_received", "first"), text=("description", "first"))
    per = per[(per["n"] == 1) & per["text"].str.len().ge(40)]
    per["label"] = per["prefix"].map(component_groups())
    per["received"] = pd.to_datetime(per["received"], format="%Y%m%d", errors="coerce")
    return per.dropna(subset=["label", "received"])


def sample(df: pd.DataFrame, per_class: int) -> pd.DataFrame:
    return df.sample(frac=1, random_state=SEED).groupby("label").head(per_class)


def main() -> None:
    data = labeled_complaints()
    train = sample(data[data["received"] < CUTOFF], TRAIN_PER_CLASS)
    test = sample(data[data["received"] >= CUTOFF], TEST_PER_CLASS)
    print(f"train {len(train)}  test {len(test)}  classes {train['label'].nunique()}", flush=True)

    t = time.time()
    x_train = embed(train["text"].tolist())
    x_test = embed(test["text"].tolist())
    embed_s = time.time() - t

    clf = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")
    clf.fit(x_train, train["label"])
    pred = clf.predict(x_test)
    report = classification_report(test["label"], pred, output_dict=True, zero_division=0)
    print(classification_report(test["label"], pred, zero_division=0))

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, ARTIFACTS / "classifier.joblib")
    metrics = {
        "model": MODEL_ID, "embedding_model": MODEL_NAME, "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "split": {"train_received_before": str(CUTOFF.date()), "test_received_from": str(CUTOFF.date()),
                  "train_rows": len(train), "test_rows": len(test)},
        "accuracy": round(report["accuracy"], 4),
        "macro": {k: round(v, 4) for k, v in report["macro avg"].items() if k != "support"},
        "per_class": {c: {k: round(v, 4) for k, v in m.items()} for c, m in report.items()
                      if c not in ("accuracy", "macro avg", "weighted avg")},
        "embed_texts_per_s": round((len(train) + len(test)) / embed_s, 1),
    }
    (ARTIFACTS / "offline_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({k: metrics[k] for k in ("accuracy", "macro")}, indent=2))


if __name__ == "__main__":
    np.random.seed(SEED)
    main()
