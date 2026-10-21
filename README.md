# Is College Worth It? A College ROI Analysis

[![CI](https://github.com/Daniels-not/college-roi/actions/workflows/ci.yml/badge.svg)](https://github.com/Daniels-not/college-roi/actions/workflows/ci.yml)

An end-to-end analysis of return on investment across ~2,000 U.S. four-year colleges, built on the U.S. Department of Education's **College Scorecard**.

**Live dashboard:** _add your Streamlit link here_ · **Tableau version:** _add your Tableau Public link here_

## What it does

- **Cost-of-living-adjusted earnings.** $50k in Alabama goes further than $50k in California. Earnings are divided by the Bureau of Economic Analysis (BEA) Regional Price Parity for the school's state.
- **Value-added ranking.** A regression predicts each school's graduate earnings from what the school *doesn't* control: incoming SAT scores, Pell share, selectivity, size, sector and region. The gap between actual and predicted earnings is the school's value added, which separates what a school adds from who it admits.
- **Controlled HBCU comparison.** Raw vs. controlled HBCU earnings gap with robust (HC3) 95% confidence intervals.
- **Peer groups.** K-means clustering (k chosen by silhouette score) groups schools that look alike, so each school is compared with real peers.
- **Interactive dashboard.** Streamlit app with rankings, a map, a school explorer, the HBCU analysis and peer groups.

## Findings

_Fill in after running on real data (see `notebooks/analysis.ipynb`, section 6)._

1. …
2. …
3. …

## Architecture

```
College Scorecard API ─► client.py   pagination, retries, exponential backoff
                           │
                           ▼
                  data/raw/*.jsonl    untouched API snapshots (auditable)
                           │
                           ▼
          DuckDB  raw_institutions · raw_programs
                           │
              dbt build    │  seeds: BEA price parities
                           │  staging: type-safe cleaning     + 20 data tests
                           │  marts: ROI metrics, HBCU summary
                           ▼
                 mart_institution_roi
                           │
           models.py       │  OLS value-added (statsmodels, HC3)
                           │  HBCU raw vs. controlled
                           │  K-means peer groups (scikit-learn)
                           ▼
    exports/  Parquet ─► Streamlit dashboard
              CSV     ─► Tableau / Power BI
```

GitHub Actions runs lint, tests and a full demo pipeline on every push, and refreshes the data monthly.

## Metrics

| Metric | Definition |
|---|---|
| `earnings_10yr_adj` | Median earnings 10 yrs after entry ÷ state price index (BEA RPP 2023) |
| `value_added_pct` | Actual ÷ predicted adjusted earnings − 1 (regression residual) |
| `debt_to_earnings` | Median completer debt ÷ median 10-yr earnings |
| `payback_years` | Median debt ÷ (10% of earnings); ignores interest, kept simple on purpose |
| `net_cost_4yr` | Average annual net price × 4 |

## Quick start

Full step-by-step instructions are in **[SETUP.md](SETUP.md)**.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,analysis]"
python -m scorecard demo                  # try everything on synthetic data, no key needed
cp .env.example .env                      # then add your free API key
python -m scorecard check-fields          # 1 API call: verifies field names
python -m scorecard all                   # ingest -> dbt -> models -> export -> summary
streamlit run app/streamlit_app.py
pytest
```

| Command | What it does |
|---|---|
| `check-fields` | One API call; reports how filled-in each configured field is |
| `ingest` | Pull from the API into DuckDB (+ raw JSONL snapshot) |
| `transform` | `dbt build`: seed, staging, marts, data tests |
| `model` | Value-added model, HBCU comparison, peer groups |
| `export` | Parquet for the dashboard, CSV for Tableau |
| `summary` | Data quality + headline results |
| `all` | Every step above, in order |
| `demo` | Full pipeline on **synthetic** data in `data/demo/` (never touches real outputs) |

## Methodology notes and limitations

- **Universe:** operating institutions whose predominant degree is the bachelor's.
- **Earnings** cover federal aid recipients only, measured 10 years after *entry*.
- **Cost of living** uses the school's state; graduates may live elsewhere. Territories have no BEA index and are left unadjusted (flagged with `has_price_index`).
- **Missing SAT** (test-optional schools) is median-imputed with a `sat_missing` flag, so not reporting a score can carry its own signal.
- **Value added is a residual, not a causal effect.** Unobserved differences between students (major choice, family networks) still end up in it.
- **Suppressed values** (small cohorts) become `NULL` in staging; the summary reports missingness for each key field.

## Project structure

```
src/scorecard/    client · ingest · transform · models · export · synthetic · CLI
dbt/              seeds (BEA RPP) · staging · marts · custom data tests
app/              Streamlit dashboard
notebooks/        analysis walkthrough
docs/tableau.md   rebuilding the dashboard in Tableau Public / Power BI
exports/          dashboard + Tableau data (committed; refreshed monthly by CI)
tests/            mocked-API, pipeline, dbt and model tests
```

## Data sources

- U.S. Department of Education, [College Scorecard](https://collegescorecard.ed.gov/data/)
- U.S. Bureau of Economic Analysis, Regional Price Parities by State, 2023 ([release 24-59, Dec 2024](https://www.bea.gov/sites/default/files/2024-12/rpp1224.pdf))
