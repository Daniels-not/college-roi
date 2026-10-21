"""Extract + load: pull from the API, keep an untouched raw copy, load DuckDB.

Layering:
  data/raw/*.jsonl      exact API records (reproducible, auditable)
  raw_* tables          same data, one column per field, renamed
  stg_* / mart_*        cleaned + derived by dbt (see dbt/)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from . import config
from .client import ScorecardClient
from .export import set_run_source

log = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_jsonl(records: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.info("wrote %d records -> %s", len(records), path)
    return path


def load_table(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> None:
    df = df.copy()
    df["_loaded_at"] = pd.Timestamp.now(tz="UTC")
    con.register("_incoming", df)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _incoming")
    con.unregister("_incoming")
    log.info("loaded %d rows -> %s", len(df), table)


# --- Institutions ------------------------------------------------------------


def fetch_institutions(client: ScorecardClient, max_pages: int | None = None) -> list[dict]:
    fields = list(config.INSTITUTION_FIELDS)
    return list(client.iter_results(fields, config.BASE_FILTERS, max_pages=max_pages))


def institutions_to_frame(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)
    # Guarantee every configured column exists even if the API omitted it.
    for api_name in config.INSTITUTION_FIELDS:
        if api_name not in df.columns:
            df[api_name] = None
    df = df[list(config.INSTITUTION_FIELDS)].rename(columns=config.INSTITUTION_FIELDS)
    return df.drop_duplicates(subset="unitid")


# --- Programs (field of study) ----------------------------------------------


def fetch_programs(client: ScorecardClient, max_pages: int | None = None) -> list[dict]:
    fields = ["id", "school.name", config.PROGRAMS_FIELD]
    filters = {**config.BASE_FILTERS, **config.PROGRAM_FILTERS}
    return list(client.iter_results(fields, filters, max_pages=max_pages))


def programs_to_frame(records: list[dict]) -> pd.DataFrame:
    """Explode each school's nested program array into one row per program."""
    rows: list[dict] = []
    for rec in records:
        programs = rec.get(config.PROGRAMS_FIELD) or []
        if isinstance(programs, dict):  # single program comes back unwrapped sometimes
            programs = [programs]
        for prog in programs:
            flat = pd.json_normalize(prog, sep="__").to_dict(orient="records")[0]
            flat["unitid"] = rec.get("id")
            flat["school_name"] = rec.get("school.name")
            rows.append(flat)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.columns = [c.replace(".", "__") for c in df.columns]
    lead = ["unitid", "school_name"]
    return df[lead + [c for c in df.columns if c not in lead]]


# --- Orchestration -------------------------------------------------------------


def run_ingest(
    client: ScorecardClient,
    db_path: Path = config.DB_PATH,
    raw_dir: Path = config.RAW_DIR,
    max_pages: int | None = None,
    include_programs: bool = True,
) -> dict[str, int]:
    ts = _timestamp()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    with duckdb.connect(str(db_path)) as con:
        inst = fetch_institutions(client, max_pages=max_pages)
        write_jsonl(inst, raw_dir / f"institutions_{ts}.jsonl")
        inst_df = institutions_to_frame(inst)
        load_table(con, "raw_institutions", inst_df)
        counts["institutions"] = len(inst_df)

        if include_programs:
            progs = fetch_programs(client, max_pages=max_pages)
            write_jsonl(progs, raw_dir / f"programs_{ts}.jsonl")
            prog_df = programs_to_frame(progs)
            if prog_df.empty:
                log.warning("No program rows returned; skipping raw_programs load")
            else:
                load_table(con, "raw_programs", prog_df)
            counts["programs"] = len(prog_df)

        set_run_source(con, "api")

    return counts


def check_fields(client: ScorecardClient, sample_pages: int = 1) -> pd.DataFrame:
    """Report how often each configured field is populated in a sample.

    A field that is 0% populated is almost always a wrong name in config.py.
    """
    records = fetch_institutions(client, max_pages=sample_pages)
    df = pd.DataFrame.from_records(records)
    rows = []
    for api_name, local in config.INSTITUTION_FIELDS.items():
        present = api_name in df.columns
        pct = float(df[api_name].notna().mean() * 100) if present and len(df) else 0.0
        rows.append({"api_field": api_name, "column": local, "pct_populated": round(pct, 1)})
    return pd.DataFrame(rows).sort_values("pct_populated")
