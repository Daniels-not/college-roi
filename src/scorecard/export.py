"""Write analysis outputs for the dashboard (Parquet) and Tableau/Power BI (CSV)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from . import config

log = logging.getLogger(__name__)

SCHOOLS_QUERY = """
select
    m.*,
    v.predicted_earnings_adj,
    v.value_added_pct,
    v.value_added_rank,
    v.value_added_pctile,
    p.peer_group,
    p.peer_group_label
from mart_institution_roi m
left join model_value_added v using (unitid)
left join model_peer_groups p using (unitid)
order by v.value_added_rank nulls last
"""


def set_run_source(con: duckdb.DuckDBPyConnection, source: str) -> None:
    """Record whether the database holds real API data or synthetic demo data."""
    con.execute("create table if not exists _run_metadata (key varchar primary key, value varchar)")
    con.execute("insert or replace into _run_metadata values ('source', ?)", [source])


def get_run_source(con: duckdb.DuckDBPyConnection) -> str:
    try:
        row = con.execute("select value from _run_metadata where key = 'source'").fetchone()
        return row[0] if row else "unknown"
    except duckdb.CatalogException:
        return "unknown"


def run_export(db_path: Path = config.DB_PATH, export_dir: Path = config.EXPORT_DIR) -> dict:
    tableau = export_dir / "tableau"
    tableau.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db_path), read_only=True) as con:
        schools = con.execute(SCHOOLS_QUERY).df()
        tables = {
            "model_coefficients": con.execute("select * from model_coefficients").df(),
            "model_fit": con.execute("select * from model_fit").df(),
            "peer_group_profile": con.execute(
                "select * from model_peer_group_profile order by peer_group"
            ).df(),
            "hbcu_summary": con.execute("select * from mart_hbcu_summary").df(),
        }
        source = get_run_source(con)

    schools.to_parquet(export_dir / "schools.parquet", index=False)
    schools.to_csv(tableau / "schools.csv", index=False)
    for name, df in tables.items():
        df.to_parquet(export_dir / f"{name}.parquet", index=False)
        df.to_csv(tableau / f"{name}.csv", index=False)

    meta = {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_schools": int(len(schools)),
    }
    (export_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    log.info("exported %d schools -> %s", len(schools), export_dir)
    return meta
