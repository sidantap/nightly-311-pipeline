"""Run the nightly pipeline end to end and record the run.

    python -m pipeline.run                 # everything
    python -m pipeline.run --steps transform,classify
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid

from . import ingest_311, ingest_nhtsa, ingest_weather
from .warehouse import ROOT, connect, log

STEPS = ["ingest", "transform", "classify", "publish"]


def dbt(*args: str, check: bool = True) -> None:
    env = {**os.environ, "DBT_PROFILES_DIR": str(ROOT / "dbt")}
    subprocess.run(["dbt", *args], cwd=ROOT / "dbt", env=env, check=check)


def ensure_weather_table() -> None:
    con = connect()
    con.execute("""create table if not exists raw.weather_daily (
        date varchar, datatype varchar, station varchar, attributes varchar, value double,
        _batch_id varchar, _ingested_at timestamp)""")
    con.close()


def step_ingest() -> dict:
    out = {"cincy_311": ingest_311.run(), "nhtsa": ingest_nhtsa.run()}
    if os.environ.get("NOAA_TOKEN"):
        out["weather"] = ingest_weather.run()
    elif os.environ.get("CI"):
        raise RuntimeError("NOAA_TOKEN secret is missing")
    else:
        log("ingest", "NOAA_TOKEN not set, skipping weather (local run)")
        ensure_weather_table()
    return out


def step_transform() -> dict:
    dbt("seed", "--quiet")
    # Stale sources fail the run in CI. Locally weather is often skipped, so only report.
    dbt("source", "freshness", check=bool(os.environ.get("CI")))
    dbt("build", "--exclude", "gold")
    return {"dbt": "silver ok"}


def step_classify() -> dict:
    from ml import predict
    return predict.run()


def step_publish() -> dict:
    dbt("build", "--select", "gold")
    return {"dbt": "gold ok"}


def step_export() -> dict:
    from . import export_site
    return export_site.run()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default=",".join(STEPS))
    ap.add_argument("--no-export", action="store_true", help="skip writing site/data.json")
    args = ap.parse_args()
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]

    run_id = f"nightly_{dt.date.today():%Y-%m-%d}_{uuid.uuid4().hex[:6]}"
    con = connect()
    con.execute("insert into meta.runs values (?, now(), null, 'running', null)", [run_id])
    con.close()
    log("run", "started", run_id=run_id, steps=steps)

    results, status = {}, "succeeded"
    for name in steps:
        t = time.time()
        try:
            results[name] = {"ok": True, **globals()[f"step_{name}"](), "seconds": round(time.time() - t, 1)}
        except Exception as e:  # record the failure, then stop: later steps depend on earlier ones
            results[name] = {"ok": False, "error": str(e)[:500], "seconds": round(time.time() - t, 1)}
            status = "failed"
            log("run", f"step {name} failed", error=str(e)[:300])
            break

    con = connect()
    con.execute("update meta.runs set finished_at = now(), status = ?, steps = ? where run_id = ?",
                [status, json.dumps(results, default=str), run_id])
    con.close()
    log("run", status, run_id=run_id)
    # Export after the run is recorded, so the dashboard shows this run's outcome, failed or not.
    if not args.no_export:
        step_export()
    return 0 if status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
