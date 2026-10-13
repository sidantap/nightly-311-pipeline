"""NHTSA vehicle safety complaints -> raw.nhtsa_complaints (bronze).

NHTSA republishes the current five-year complaints file every day. We download it,
keep rows added since the watermark (DATEA) minus an overlap, and land them as
received. One complaint (ODINO) can have several rows, one per component.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import uuid
import zipfile

import pandas as pd
import requests

from .warehouse import append, connect, get_watermark, log, set_watermark, today

SOURCE = "nhtsa_complaints"
BASE = "https://static.nhtsa.gov/odi/ffdd/cmpl/"
OVERLAP_DAYS = 3
# Field positions from NHTSA's CMPL.txt layout (0-based)
FIELDS = {0: "cmplid", 1: "odino", 2: "mfr_name", 3: "make", 4: "model", 5: "model_year",
          6: "crash", 7: "fail_date", 8: "fire", 9: "injured", 10: "deaths", 11: "component",
          13: "state", 15: "date_added", 16: "date_received", 17: "miles", 19: "description",
          20: "complaint_type"}


def current_file(year: int) -> str:
    start = 2025 + 5 * ((year - 2025) // 5)
    return f"COMPLAINTS_RECEIVED_{start}-{year}.zip"


def download(year: int) -> pd.DataFrame:
    name = current_file(year)
    log("ingest", "downloading NHTSA file", file=name)
    r = requests.get(BASE + name, headers={"User-Agent": "Mozilla/5.0 nightly-311-pipeline"}, timeout=600)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(z.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw), sep="\t", header=None, dtype="string", quoting=csv.QUOTE_NONE,
                     encoding="latin-1", usecols=list(FIELDS), on_bad_lines="skip")
    return df.rename(columns=FIELDS)[list(FIELDS.values())]


def run() -> dict:
    con = connect()
    wm = get_watermark(con, SOURCE)
    if wm:
        since = dt.date.fromisoformat(wm) - dt.timedelta(days=OVERLAP_DAYS)
    else:
        since = today() - dt.timedelta(days=int(os.environ.get("NHTSA_BACKFILL_DAYS", "7")))
        log("ingest", "NHTSA first run, backfilling", since=since)

    df = download(today().year)
    added = pd.to_datetime(df["date_added"], format="%Y%m%d", errors="coerce")
    df = df[added >= pd.Timestamp(since)].copy()
    df["_batch_id"] = uuid.uuid4().hex[:12]
    df["_ingested_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)

    append(con, f"raw.{SOURCE}", df)
    if len(df):
        newest = pd.to_datetime(df["date_added"], format="%Y%m%d", errors="coerce").max()
        set_watermark(con, SOURCE, newest.date().isoformat())
    stats = {"rows": len(df), "complaints": int(df["odino"].nunique()), "since": since.isoformat(),
             "watermark": get_watermark(con, SOURCE)}
    log("ingest", "NHTSA landed in bronze", **stats)
    con.close()
    return stats


if __name__ == "__main__":
    run()
