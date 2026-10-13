"""Warehouse connection, bookkeeping tables and watermark helpers."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import duckdb
import pyarrow as pa

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("WAREHOUSE_PATH", ROOT / "warehouse" / "warehouse.duckdb"))


def connect() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("create schema if not exists raw")
    con.execute("create schema if not exists meta")
    con.execute("create schema if not exists ml")
    con.execute(
        """create table if not exists meta.watermarks (
             source varchar primary key,
             watermark varchar not null,
             updated_at timestamp not null)"""
    )
    con.execute(
        """create table if not exists meta.runs (
             run_id varchar primary key,
             started_at timestamp not null,
             finished_at timestamp,
             status varchar not null,
             steps json)"""
    )
    return con


def get_watermark(con, source: str) -> str | None:
    row = con.execute("select watermark from meta.watermarks where source = ?", [source]).fetchone()
    return row[0] if row else None


def set_watermark(con, source: str, value: str) -> None:
    """Advance a source's watermark. Called only after its load has committed."""
    con.execute(
        """insert into meta.watermarks values (?, ?, now())
           on conflict (source) do update set watermark = excluded.watermark, updated_at = excluded.updated_at""",
        [source, value],
    )


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def log(step: str, msg: str, **fields) -> None:
    extra = (" " + json.dumps(fields, default=str)) if fields else ""
    print(f"{dt.datetime.now(dt.timezone.utc):%H:%M:%S}  {step:<9} {msg}{extra}", flush=True)


def append(con, table: str, df) -> None:
    """Append a DataFrame to a raw table, creating it on first use. Goes through Arrow
    so pandas' string dtype maps cleanly to VARCHAR."""
    tbl = pa.Table.from_pandas(df, preserve_index=False)
    con.register("_incoming", tbl)
    con.execute(f"create table if not exists {table} as select * from _incoming where false")
    con.execute(f"insert into {table} by name select * from _incoming")
    con.unregister("_incoming")
