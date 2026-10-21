"""Command-line entry point.

python -m scorecard check-fields   verify field names (1 API call)
python -m scorecard ingest         pull from the API into DuckDB
python -m scorecard transform      dbt build: seeds, staging, marts, data tests
python -m scorecard model          value-added model, HBCU comparison, peer groups
python -m scorecard export         Parquet for the dashboard, CSV for Tableau
python -m scorecard summary        data-quality + headline results
python -m scorecard all            every step above, in order
python -m scorecard demo           full pipeline on SYNTHETIC data (no API key)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

from . import config
from .client import ScorecardClient, ScorecardError
from .export import run_export
from .ingest import check_fields, run_ingest
from .models import hbcu_gap, run_models
from .transform import TransformError, data_quality_report, run_transforms


def _summary(db_path: Path) -> None:
    print("\n=== Data quality ===")
    for k, v in data_quality_report(db_path).items():
        print(f"  {k:<24} {v}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        print("\n=== HBCU vs. non-HBCU (raw medians) ===")
        print(con.execute("select * from mart_hbcu_summary").df().to_string(index=False))

        tables = {r[0] for r in con.execute("show tables").fetchall()}
        if "model_coefficients" not in tables:
            print("\n(run `model` for value-added and controlled HBCU results)")
            return

        fit = con.execute("select * from model_fit").df()
        print("\n=== Model fit ===")
        print(fit.round(3).to_string(index=False))

        gap = hbcu_gap(con.execute("select * from model_coefficients").df())
        if len(gap):
            print("\n=== HBCU earnings gap (log points; pct_effect = approx % difference) ===")
            print(gap.round(4).to_string(index=False))

        top = con.execute("""
            select m.name, m.state, m.earnings_10yr_adj, v.predicted_earnings_adj,
                   round(v.value_added_pct * 100, 1) as value_added_pct
            from model_value_added v join mart_institution_roi m using (unitid)
            order by v.value_added_rank limit 10
        """).df()
        print("\n=== Top 10 by value added ===")
        print(top.to_string(index=False))


def _run_pipeline(db_path: Path, export_dir: Path) -> None:
    run_transforms(db_path)
    result = run_models(db_path)
    print(
        f"Modeled {result['schools_modeled']} schools; "
        f"value-added R² = {result['value_added_r2']}; {result['peer_groups']} peer groups"
    )
    meta = run_export(db_path, export_dir)
    print(f"Exported {meta['n_schools']} schools ({meta['source']} data) -> {export_dir}")
    _summary(db_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scorecard")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check-fields")
    for name in ("ingest", "all"):
        p = sub.add_parser(name)
        p.add_argument(
            "--max-pages",
            type=int,
            default=None,
            help="limit pages per pull (useful with DEMO_KEY)",
        )
        p.add_argument("--skip-programs", action="store_true")
    for name in ("transform", "model", "export", "summary"):
        sub.add_parser(name)
    d = sub.add_parser("demo", help="run everything on synthetic data, no API key needed")
    d.add_argument("--n", type=int, default=1500, help="number of fake schools")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    pd.set_option("display.width", 160)
    db = config.DB_PATH

    try:
        if args.cmd == "check-fields":
            report = check_fields(ScorecardClient())
            print(report.to_string(index=False))
            bad = report[report.pct_populated == 0]
            if len(bad):
                print(f"\n{len(bad)} field(s) returned no data; check names in config.py")
            return 0

        if args.cmd == "demo":
            from .synthetic import load_demo

            n = load_demo(config.DEMO_DB_PATH, n=args.n)
            print(f"Loaded {n} SYNTHETIC schools (demo only, not real data)")
            _run_pipeline(config.DEMO_DB_PATH, config.DEMO_EXPORT_DIR)
            return 0

        if args.cmd in ("ingest", "all"):
            counts = run_ingest(
                ScorecardClient(),
                max_pages=args.max_pages,
                include_programs=not args.skip_programs,
            )
            print(f"Ingested: {counts}")
        if args.cmd == "all":
            _run_pipeline(db, config.EXPORT_DIR)
            return 0

        if args.cmd == "transform":
            run_transforms(db)
        elif args.cmd == "model":
            result = run_models(db)
            print({k: v for k, v in result.items() if k != "hbcu_gap"})
        elif args.cmd == "export":
            print(run_export(db))
        elif args.cmd == "summary":
            _summary(db)
    except (ScorecardError, TransformError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
