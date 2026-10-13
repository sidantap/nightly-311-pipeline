"""Cincinnati 311 service requests -> raw.cincy_311 (bronze).

Incremental on date_last_update. Requests change after they are created (status,
close date), so each run re-reads a two-day overlap behind the watermark and lands
every version as received. Silver keeps the latest version of each request.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import uuid

import pandas as pd
import requests

from .warehouse import append, connect, get_watermark, log, set_watermark, today

SOURCE = "cincy_311"
URL = "https://data.cincinnati-oh.gov/resource/gcej-gmiw.json"
COLUMNS = [
    "sr_number", "sr_type", "sr_type_desc", "priority", "dept_name", "dept_division",
    "neighborhood", "zipcode", "method_received", "date_created", "time_received",
    "date_closed", "sr_status", "sr_status_flag", "date_last_update", "time_last_update",
    "planned_completion_days", "latitude", "longitude",
]
PAGE = 20_000
RETRIES = 4
OVERLAP_DAYS = 2


def fetch(since: dt.date) -> pd.DataFrame:
    # Every request has date_last_update >= date_created, so one indexed filter covers new and changed rows.
    where = f"date_last_update >= '{since.isoformat()}'"
    frames, offset = [], 0
    session = requests.Session()
    session.headers["User-Agent"] = "nightly-311-pipeline (github.com/sidantap/nightly-311-pipeline)"
    if token := os.environ.get("SOCRATA_APP_TOKEN"):
        session.headers["X-App-Token"] = token
    while True:
        params = {"$select": ",".join(COLUMNS), "$where": where, "$order": "sr_number",
                  "$limit": PAGE, "$offset": offset}
        for attempt in range(1, RETRIES + 1):
            try:
                r = session.get(URL, params=params, timeout=180)
                if r.status_code < 500:
                    break
                err = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                err = type(e).__name__
            if attempt == RETRIES:
                raise RuntimeError(f"311 API failed {RETRIES} times at offset {offset}: {err}")
            log("ingest", "311 API slow or failing, retrying", attempt=attempt, error=err, wait_s=10 * attempt)
            time.sleep(10 * attempt)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        frames.append(pd.DataFrame(rows))
        offset += len(rows)
        log("ingest", f"311 page read", rows=offset)
        if len(rows) < PAGE:
            break
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    return df.reindex(columns=COLUMNS).astype("string")


def run() -> dict:
    con = connect()
    wm = get_watermark(con, SOURCE)
    if wm:
        since = dt.date.fromisoformat(wm) - dt.timedelta(days=OVERLAP_DAYS)
    else:
        since = today() - dt.timedelta(days=int(os.environ.get("BACKFILL_DAYS", "30")))
        log("ingest", "311 first run, backfilling", since=since)

    df = fetch(since)
    batch = uuid.uuid4().hex[:12]
    df["_batch_id"] = batch
    df["_ingested_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)

    append(con, f"raw.{SOURCE}", df)

    if len(df):
        newest = pd.to_datetime(df["date_last_update"], errors="coerce").max()
        if pd.notna(newest):
            set_watermark(con, SOURCE, newest.date().isoformat())
    stats = {"rows": len(df), "since": since.isoformat(), "batch": batch,
             "watermark": get_watermark(con, SOURCE)}
    log("ingest", "311 landed in bronze", **stats)
    con.close()
    return stats


if __name__ == "__main__":
    run()
