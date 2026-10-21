"""Run the dbt project (seeds, staging, marts, data tests) against DuckDB."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

from . import config

log = logging.getLogger(__name__)


class TransformError(RuntimeError):
    pass


def _dbt_executable() -> str:
    # Prefer the dbt installed in the same environment as this Python
    # (.venv/bin on Mac/Linux, .venv\Scripts on Windows).
    here = Path(sys.executable).parent
    found = shutil.which("dbt", path=str(here)) or shutil.which("dbt")
    if not found:
        raise TransformError('dbt not found. Run: pip install -e ".[dev,analysis]"')
    return found


def run_dbt(args: list[str], db_path: Path = config.DB_PATH) -> None:
    """Run dbt as a subprocess. Raises TransformError if any model or test fails.

    A subprocess (rather than dbt's in-process runner) guarantees dbt's DuckDB
    connection is closed before the modeling step opens the same file.
    """
    env = {**os.environ, "SCORECARD_DB": str(Path(db_path).resolve())}
    cmd = [
        _dbt_executable(),
        *args,
        "--project-dir",
        str(config.DBT_DIR),
        "--profiles-dir",
        str(config.DBT_DIR),
    ]
    log.info("dbt %s", " ".join(args))
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode != 0:
        raise TransformError(f"dbt {' '.join(args)} failed; see the dbt output above")


def run_transforms(db_path: Path = config.DB_PATH) -> None:
    """Seed + build every model and run every data test, in dependency order."""
    run_dbt(["build"], db_path=db_path)


def data_quality_report(db_path: Path = config.DB_PATH) -> dict[str, object]:
    """Basic checks worth showing in the README / notebook."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        total = con.execute("select count(*) from stg_institutions").fetchone()[0]
        dupes = con.execute(
            "select count(*) - count(distinct unitid) from stg_institutions"
        ).fetchone()[0]
        with_earn = con.execute("select count(*) from mart_institution_roi").fetchone()[0]
        hbcus = con.execute("select count(*) from stg_institutions where is_hbcu").fetchone()[0]
        no_rpp = con.execute(
            "select count(*) from mart_institution_roi where not has_price_index"
        ).fetchone()[0]
        nulls = con.execute(
            """
            select
              round(100.0 * count(*) filter (where median_debt is null) / count(*), 1),
              round(100.0 * count(*) filter (where net_price is null) / count(*), 1),
              round(100.0 * count(*) filter (where grad_rate is null) / count(*), 1),
              round(100.0 * count(*) filter (where sat_avg is null) / count(*), 1)
            from stg_institutions
            """
        ).fetchone()
    return {
        "institutions": total,
        "duplicate_unitids": dupes,
        "with_10yr_earnings": with_earn,
        "hbcus": hbcus,
        "outside_50_states_dc": no_rpp,
        "pct_missing_debt": nulls[0],
        "pct_missing_net_price": nulls[1],
        "pct_missing_grad_rate": nulls[2],
        "pct_missing_sat": nulls[3],
    }
