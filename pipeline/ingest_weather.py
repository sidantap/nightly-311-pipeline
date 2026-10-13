"""NOAA daily weather at Cincinnati/Northern Kentucky airport -> raw.weather_daily (bronze).

NOAA revises recent days as late observations arrive, so each run re-reads a
seven-day overlap. Silver keeps the most recently ingested value per day and metric.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import uuid

import pandas as pd
import requests

from .warehouse import append, connect, get_watermark, log, set_watermark, today

SOURCE = "weather_daily"
URL = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
STATION = "GHCND:USW00093814"  # CVG airport
DATATYPES = ["TMAX", "TMIN", "PRCP", "SNOW", "AWND"]
OVERLAP_DAYS = 7


def fetch(start: dt.date, end: dt.date, token: str) -> pd.DataFrame:
    rows: list[dict] = []
    session = requests.Session()
    session.headers["token"] = token
    # CDO caps a request at one year and 1,000 rows, so walk in 90-day windows and pages.
    win_start = start
    while win_start <= end:
        win_end = min(win_start + dt.timedelta(days=89), end)
        offset = 1
        while True:
            params = {"datasetid": "GHCND", "stationid": STATION, "datatypeid": DATATYPES,
                      "startdate": win_start.isoformat(), "enddate": win_end.isoformat(),
                      "units": "standard", "limit": 1000, "offset": offset}
            for attempt in range(4):
                r = session.get(URL, params=params, timeout=60)
                if r.status_code in (429, 500, 502, 503):
                    wait = 2 ** (attempt + 1)
                    log("ingest", f"NOAA {r.status_code}, retrying", attempt=attempt + 1, wait_s=wait)
                    time.sleep(wait)
                    continue
                break
            r.raise_for_status()
            body = r.json() if r.text.strip() else {}
            page = body.get("results", [])
            rows.extend(page)
            meta = body.get("metadata", {}).get("resultset", {})
            if not page or offset + len(page) > meta.get("count", 0):
                break
            offset += len(page)
            time.sleep(0.25)  # stay under 5 requests/second
        win_start = win_end + dt.timedelta(days=1)
    df = pd.DataFrame(rows, columns=["date", "datatype", "station", "attributes", "value"])
    return df.astype({"date": "string", "datatype": "string", "station": "string",
                      "attributes": "string", "value": "float64"})


def run() -> dict:
    token = os.environ.get("NOAA_TOKEN")
    if not token:
        raise RuntimeError("NOAA_TOKEN is not set")
    con = connect()
    wm = get_watermark(con, SOURCE)
    end = today()
    if wm:
        start = dt.date.fromisoformat(wm) - dt.timedelta(days=OVERLAP_DAYS)
    else:
        start = end - dt.timedelta(days=int(os.environ.get("BACKFILL_DAYS", "30")))
        log("ingest", "weather first run, backfilling", since=start)

    df = fetch(start, end, token)
    df["_batch_id"] = uuid.uuid4().hex[:12]
    df["_ingested_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)
    append(con, f"raw.{SOURCE}", df)
    if len(df):
        set_watermark(con, SOURCE, pd.to_datetime(df["date"]).max().date().isoformat())
    stats = {"rows": len(df), "since": start.isoformat(), "watermark": get_watermark(con, SOURCE)}
    log("ingest", "weather landed in bronze", **stats)
    con.close()
    return stats


if __name__ == "__main__":
    run()
