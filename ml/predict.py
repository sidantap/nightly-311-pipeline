"""Nightly: classify complaints that don't have a prediction yet, then score the
model on every labeled complaint it has predicted in the last 30 days.

The model never sees the official component label; it is used only for scoring.
"""
from __future__ import annotations

import datetime as dt
import json

import joblib
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from ml.common import ARTIFACTS, MODEL_ID, embed
from pipeline.warehouse import append, connect, log

WINDOW_DAYS = 30


def predict_new(con) -> int:
    con.execute("""create table if not exists ml.predictions (
        complaint_id varchar, model varchar, predicted_group varchar,
        confidence double, predicted_at timestamp)""")
    todo = con.execute("""
        select c.complaint_id, c.description
        from silver.complaints c
        where not exists (select 1 from ml.predictions p
                          where p.complaint_id = c.complaint_id and p.model = ?)""", [MODEL_ID]).df()
    if todo.empty:
        return 0
    clf = joblib.load(ARTIFACTS / "classifier.joblib")
    proba = clf.predict_proba(embed(todo["description"].tolist()))
    out = pd.DataFrame({
        "complaint_id": todo["complaint_id"],
        "model": MODEL_ID,
        "predicted_group": clf.classes_[proba.argmax(axis=1)],
        "confidence": proba.max(axis=1).round(4),
        "predicted_at": pd.Timestamp.now(tz="UTC").tz_localize(None),
    })
    append(con, "ml.predictions", out)
    return len(out)


def score(con) -> dict:
    df = con.execute(f"""
        select c.component_group as actual, p.predicted_group as predicted
        from ml.predictions p join silver.complaints c using (complaint_id)
        where p.model = ? and c.component_group is not null
          and c.received_date >= current_date - interval {WINDOW_DAYS} day""", [MODEL_ID]).df()
    if df.empty:
        return {"rows": 0}
    p, r, f, _ = precision_recall_fscore_support(df["actual"], df["predicted"], average="macro", zero_division=0)
    metrics = {"model": MODEL_ID, "window_days": WINDOW_DAYS, "rows": len(df),
               "accuracy": round(float((df["actual"] == df["predicted"]).mean()), 4),
               "macro_precision": round(float(p), 4), "macro_recall": round(float(r), 4),
               "macro_f1": round(float(f), 4)}
    con.execute("""create table if not exists ml.live_metrics (
        scored_on date, model varchar, rows integer, accuracy double,
        macro_precision double, macro_recall double, macro_f1 double)""")
    con.execute("delete from ml.live_metrics where scored_on = current_date and model = ?", [MODEL_ID])
    con.execute("insert into ml.live_metrics values (current_date, ?, ?, ?, ?, ?, ?)",
                [MODEL_ID, metrics["rows"], metrics["accuracy"], metrics["macro_precision"],
                 metrics["macro_recall"], metrics["macro_f1"]])
    return metrics


def run() -> dict:
    con = connect()
    n = predict_new(con)
    log("classify", "new complaints classified", rows=n)
    metrics = score(con)
    log("classify", "live score, last 30 days", **metrics)
    con.close()
    return {"classified": n, **metrics}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
