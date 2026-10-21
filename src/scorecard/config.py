"""Project configuration: paths, API settings, and the field map.

The field map is the single source of truth for which College Scorecard
variables we pull and what we call them locally. Dotted names come from the
"dev-category" + "developer-friendly name" columns of the official Data
Dictionary. Run `python -m scorecard check-fields` after changing this map to
confirm every field actually returns data.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.getenv("SCORECARD_DB", DATA_DIR / "scorecard.duckdb")).resolve()
DBT_DIR = ROOT / "dbt"
EXPORT_DIR = ROOT / "exports"
# Demo mode (synthetic data) lives entirely under data/demo so it can never
# overwrite the real database or the committed exports.
DEMO_DIR = DATA_DIR / "demo"
DEMO_DB_PATH = DEMO_DIR / "demo.duckdb"
DEMO_EXPORT_DIR = DEMO_DIR / "exports"

# --- Modeling ----------------------------------------------------------------
RANDOM_STATE = 42
CLUSTER_K_RANGE = range(3, 9)  # candidate peer-group counts, picked by silhouette

# --- API -------------------------------------------------------------------
API_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"
API_KEY = os.getenv("SCORECARD_API_KEY", "")
PER_PAGE = 100  # API maximum
REQUEST_TIMEOUT = 60  # seconds

# Universe: currently operating schools that predominantly award bachelor's
# degrees (predominant degree code 3). Roughly 2,000 institutions.
BASE_FILTERS: dict[str, str] = {
    "school.degrees_awarded.predominant": "3",
    "school.operating": "1",
}

# --- Institution fields: API dotted name -> local column name ---------------
INSTITUTION_FIELDS: dict[str, str] = {
    "id": "unitid",
    "school.name": "name",
    "school.city": "city",
    "school.state": "state",
    "school.region_id": "region_id",
    "school.locale": "locale",
    "school.ownership": "ownership",
    "school.minority_serving.historically_black": "is_hbcu",
    "location.lat": "lat",
    "location.lon": "lon",
    "latest.student.size": "enrollment",
    "latest.admissions.admission_rate.overall": "admission_rate",
    "latest.admissions.sat_scores.average.overall": "sat_avg",
    "latest.cost.tuition.in_state": "tuition_in_state",
    "latest.cost.tuition.out_of_state": "tuition_out_of_state",
    "latest.cost.avg_net_price.public": "net_price_public",
    "latest.cost.avg_net_price.private": "net_price_private",
    "latest.aid.pell_grant_rate": "pell_rate",
    "latest.aid.federal_loan_rate": "federal_loan_rate",
    "latest.aid.median_debt.completers.overall": "median_debt_completers",
    "latest.completion.completion_rate_4yr_150nt": "grad_rate_150",
    "latest.student.retention_rate.four_year.full_time": "retention_rate",
    "latest.earnings.6_yrs_after_entry.median": "earnings_6yr_median",
    "latest.earnings.10_yrs_after_entry.median": "earnings_10yr_median",
}

# --- Field-of-study (program) pull -----------------------------------------
PROGRAMS_FIELD = "latest.programs.cip_4_digit"
# Credential level 3 = bachelor's degree. Filtering on a nested field makes the
# API return only matching programs inside each school's array.
PROGRAM_FILTERS: dict[str, str] = {
    f"{PROGRAMS_FIELD}.credential.level": "3",
}
