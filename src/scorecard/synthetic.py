"""Synthetic College-Scorecard-shaped data for demos, tests, and CI.

THIS IS FAKE DATA. It exists so the whole pipeline (dbt, models, dashboard)
can run without an API key. Anything built from it is labelled "demo" and the
dashboard shows a warning banner. Never quote numbers from it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

STATES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "PR",
]
# Rough state centroids, only so the demo map has points in sensible places.
CENTROIDS = {
    "AL": (32.8, -86.8),
    "AK": (61.4, -150.0),
    "AZ": (34.2, -111.7),
    "AR": (34.9, -92.4),
    "CA": (36.8, -119.4),
    "CO": (39.0, -105.5),
    "CT": (41.6, -72.7),
    "DE": (39.0, -75.5),
    "DC": (38.9, -77.0),
    "FL": (28.6, -82.4),
    "GA": (32.7, -83.4),
    "HI": (20.8, -156.3),
    "ID": (44.1, -114.7),
    "IL": (40.0, -89.2),
    "IN": (39.9, -86.3),
    "IA": (42.0, -93.5),
    "KS": (38.5, -98.4),
    "KY": (37.5, -85.3),
    "LA": (31.0, -92.0),
    "ME": (45.4, -69.2),
    "MD": (39.0, -76.8),
    "MA": (42.3, -71.8),
    "MI": (43.3, -84.5),
    "MN": (46.3, -94.3),
    "MS": (32.7, -89.7),
    "MO": (38.4, -92.5),
    "MT": (47.0, -109.6),
    "NE": (41.5, -99.8),
    "NV": (39.3, -116.6),
    "NH": (43.7, -71.6),
    "NJ": (40.1, -74.7),
    "NM": (34.4, -106.1),
    "NY": (42.9, -75.5),
    "NC": (35.5, -79.4),
    "ND": (47.5, -100.5),
    "OH": (40.3, -82.8),
    "OK": (35.6, -97.5),
    "OR": (43.9, -120.6),
    "PA": (40.9, -77.8),
    "RI": (41.7, -71.5),
    "SC": (33.9, -80.9),
    "SD": (44.4, -100.2),
    "TN": (35.9, -86.4),
    "TX": (31.5, -99.3),
    "UT": (39.3, -111.7),
    "VT": (44.1, -72.7),
    "VA": (37.5, -78.9),
    "WA": (47.4, -120.5),
    "WV": (38.6, -80.6),
    "WI": (44.6, -89.9),
    "WY": (43.0, -107.6),
    "PR": (18.2, -66.5),
}
HBCU_STATES = ["AL", "GA", "MS", "NC", "LA", "TX", "SC", "VA", "MD", "TN", "FL", "DC"]


def make_institution_records(n: int = 1500, seed: int = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    recs: list[dict] = []
    for i in range(n):
        is_hbcu = rng.random() < 0.05
        state = rng.choice(HBCU_STATES) if is_hbcu else rng.choice(STATES)
        ownership = int(rng.choice([1, 2, 3], p=[0.35, 0.55, 0.10]))
        enrollment = int(np.exp(rng.normal(8.0 if ownership == 1 else 7.2, 0.9)))
        sat = float(np.clip(rng.normal(1150, 130), 850, 1550))
        if is_hbcu:
            sat -= 120
        admission = float(np.clip(1.35 - sat / 1500 + rng.normal(0, 0.12), 0.04, 1.0))
        has_admission = rng.random() > 0.08  # open-admission schools report none
        pell = float(
            np.clip(
                0.75 - (sat - 850) / 1100 + rng.normal(0, 0.07) + (0.25 if is_hbcu else 0),
                0.05,
                0.95,
            )
        )
        grad = float(np.clip(0.15 + (sat - 850) / 900 + rng.normal(0, 0.08), 0.05, 0.98))
        net_price = float(
            np.clip(
                (14000 if ownership == 1 else 26000 if ownership == 2 else 21000)
                + (sat - 1150) * 15
                + rng.normal(0, 3500),
                4000,
                60000,
            )
        )
        log_earn = (
            10.80
            + (sat - 1150) / 1000
            - 0.25 * (pell - 0.35)
            + (0.0 if ownership != 3 else -0.12)
            + rng.normal(0, 0.11)
        )
        earnings = float(round(np.exp(log_earn), -2))
        debt = float(
            round(
                np.clip(rng.normal(23000, 5000) + (4000 if ownership != 1 else 0), 5000, 45000), -2
            )
        )
        lat, lon = CENTROIDS[state]

        rec = {
            "id": 900000 + i,
            "school.name": f"Demo {'HBCU ' if is_hbcu else ''}College {i:04d}",
            "school.city": "Demo City",
            "school.state": state,
            "school.region_id": int(rng.integers(1, 9)),
            "school.locale": int(rng.choice([11, 12, 21, 31, 41])),
            "school.ownership": ownership,
            "school.minority_serving.historically_black": int(is_hbcu),
            "location.lat": lat + rng.normal(0, 0.8),
            "location.lon": lon + rng.normal(0, 0.8),
            "latest.student.size": enrollment,
            "latest.admissions.admission_rate.overall": round(admission, 4)
            if has_admission
            else None,
            "latest.admissions.sat_scores.average.overall": round(sat)
            if rng.random() > 0.3
            else None,
            "latest.cost.tuition.in_state": round(net_price * 1.4, -2),
            "latest.cost.tuition.out_of_state": round(net_price * 2.0, -2),
            "latest.cost.avg_net_price.public": round(net_price, -1) if ownership == 1 else None,
            "latest.cost.avg_net_price.private": None if ownership == 1 else round(net_price, -1),
            "latest.aid.pell_grant_rate": round(pell, 4),
            "latest.aid.federal_loan_rate": round(float(np.clip(pell + 0.1, 0, 1)), 4),
            "latest.aid.median_debt.completers.overall": debt if rng.random() > 0.05 else None,
            "latest.completion.completion_rate_4yr_150nt": round(grad, 4),
            "latest.student.retention_rate.four_year.full_time": round(min(grad + 0.2, 0.99), 4),
            "latest.earnings.6_yrs_after_entry.median": round(earnings * 0.78, -2),
            "latest.earnings.10_yrs_after_entry.median": earnings if rng.random() > 0.04 else None,
        }
        recs.append(rec)
    return recs


def make_frame(n: int = 1500, seed: int = 7) -> pd.DataFrame:
    from .ingest import institutions_to_frame

    return institutions_to_frame(make_institution_records(n, seed))


def load_demo(db_path, n: int = 1500, seed: int = 7) -> int:
    """Load synthetic institutions into raw_institutions and tag the DB as demo."""
    from pathlib import Path

    import duckdb

    from .export import set_run_source
    from .ingest import load_table

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    df = make_frame(n, seed)
    with duckdb.connect(str(db_path)) as con:
        load_table(con, "raw_institutions", df)
        set_run_source(con, "demo")
    return len(df)
