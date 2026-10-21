"""Statistical models: value-added ranking, controlled HBCU comparison, peer groups.

Value added
-----------
We regress log(cost-of-living-adjusted 10-yr earnings) on things a school does
NOT control: incoming student preparation (SAT), economic background (Pell
share), selectivity, size, sector and region. The residual is how much more
(or less) a school's graduates earn than predicted for a school admitting
similar students: its "value added". Expressed as a percent: exp(resid) - 1.

HBCU comparison
---------------
Three nested OLS models with heteroskedasticity-robust (HC3) errors:
  raw         log_earn ~ is_hbcu
  controlled  log_earn ~ is_hbcu + all value-added controls
The is_hbcu coefficient moving from raw -> controlled is the headline finding.

Peer groups
-----------
K-means on standardized size, selectivity, cost, Pell share, SAT and
graduation rate. k is chosen by silhouette score.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from . import config

log = logging.getLogger(__name__)

CONTROL_TERMS = [
    "sat_z",
    "sat_missing",
    "admission_rate_f",
    "admission_missing",
    "pell_rate_f",
    "log_enrollment",
    "C(ownership)",
    "C(region_id)",
]
CLUSTER_FEATURES = [
    "log_enrollment",
    "admission_rate_f",
    "net_price_f",
    "pell_rate_f",
    "sat_f",
    "grad_rate_f",
]


# --- Data prep -----------------------------------------------------------------


def load_mart(db_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute("select * from mart_institution_roi").df()


def _impute(df: pd.DataFrame, col: str, flag: str | None = None) -> pd.Series:
    """Median-impute; optionally record which rows were imputed."""
    if flag:
        df[flag] = df[col].isna().astype(int)
    return df[col].fillna(df[col].median())


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["earnings_10yr_adj"].notna() & (df["earnings_10yr_adj"] > 0)]
    df = df[df["ownership"].notna() & df["enrollment"].notna() & (df["enrollment"] > 0)]

    df["log_earn"] = np.log(df["earnings_10yr_adj"])
    df["log_enrollment"] = np.log(df["enrollment"])
    df["is_hbcu"] = df["is_hbcu"].astype(int)
    df["region_id"] = df["region_id"].fillna(-1).astype(int)

    # Many schools are test-optional, so SAT is often missing. Impute + flag so
    # the model can learn that "missing" itself carries information.
    df["sat_f"] = _impute(df, "sat_avg", "sat_missing")
    df["sat_z"] = (df["sat_f"] - df["sat_f"].mean()) / df["sat_f"].std()
    df["admission_rate_f"] = _impute(df, "admission_rate", "admission_missing")
    df["pell_rate_f"] = _impute(df, "pell_rate")
    df["net_price_f"] = _impute(df, "net_price")
    df["grad_rate_f"] = _impute(df, "grad_rate")
    return df.reset_index(drop=True)


# --- Regression --------------------------------------------------------------------


def _tidy(result, model_name: str) -> pd.DataFrame:
    ci = result.conf_int()
    out = pd.DataFrame(
        {
            "model": model_name,
            "term": result.params.index,
            "coef": result.params.values,
            "std_err": result.bse.values,
            "ci_low": ci[0].values,
            "ci_high": ci[1].values,
            "p_value": result.pvalues.values,
        }
    )
    # Coefficients are on log earnings; convert to an approximate % effect.
    out["pct_effect"] = np.exp(out["coef"]) - 1
    return out


def build_controls(df: pd.DataFrame) -> str:
    """Control terms, minus any that don't vary in this data.

    A constant column (e.g. a missing-flag that's all 0, or only one sector
    present) is perfectly collinear with the intercept and breaks OLS.
    """
    terms = []
    for term in CONTROL_TERMS:
        col = term[2:-1] if term.startswith("C(") else term
        if df[col].nunique(dropna=True) > 1:
            terms.append(term)
        else:
            log.info("dropping constant control: %s", term)
    return " + ".join(terms)


def fit_value_added(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (per-school value added, coefficient table, fit stats)."""
    controls = build_controls(df)
    va_fit = smf.ols(f"log_earn ~ {controls}", data=df).fit(cov_type="HC3")

    schools = df[["unitid"]].copy()
    schools["predicted_earnings_adj"] = np.exp(va_fit.fittedvalues).round(0)
    schools["value_added_pct"] = (np.exp(va_fit.resid) - 1).round(4)
    schools["value_added_rank"] = (
        schools["value_added_pct"].rank(ascending=False, method="min").astype(int)
    )
    schools["value_added_pctile"] = schools["value_added_pct"].rank(pct=True).round(3)

    coefs = [_tidy(va_fit, "value_added")]
    fits = [
        {
            "model": "value_added",
            "n": int(va_fit.nobs),
            "r2": va_fit.rsquared,
            "adj_r2": va_fit.rsquared_adj,
        }
    ]

    if df["is_hbcu"].sum() >= 5:
        for name, formula in [
            ("hbcu_raw", "log_earn ~ is_hbcu"),
            ("hbcu_controlled", f"log_earn ~ is_hbcu + {controls}"),
        ]:
            res = smf.ols(formula, data=df).fit(cov_type="HC3")
            coefs.append(_tidy(res, name))
            fits.append(
                {"model": name, "n": int(res.nobs), "r2": res.rsquared, "adj_r2": res.rsquared_adj}
            )
    else:
        log.warning("Fewer than 5 HBCUs with earnings; skipping HBCU models")

    return schools, pd.concat(coefs, ignore_index=True), pd.DataFrame(fits)


def hbcu_gap(coefs: pd.DataFrame) -> pd.DataFrame:
    """The is_hbcu row from each HBCU model, i.e. the headline comparison."""
    rows = coefs[(coefs["term"] == "is_hbcu") & coefs["model"].str.startswith("hbcu_")]
    return rows[["model", "coef", "ci_low", "ci_high", "p_value", "pct_effect"]].reset_index(
        drop=True
    )


# --- Clustering -------------------------------------------------------------------


def _describe_group(g: pd.DataFrame, overall: pd.DataFrame) -> str:
    enroll = g["enrollment"].median()
    size = "Small" if enroll < 2000 else "Mid-size" if enroll < 10000 else "Large"
    sector = g["ownership"].mode().iat[0]
    sector = {
        "Public": "public",
        "Private nonprofit": "private",
        "Private for-profit": "for-profit",
    }.get(sector, sector)
    adm = g["admission_rate_f"].median()
    sel = (
        "highly selective" if adm < 0.35 else "open access" if adm > 0.8 else "moderately selective"
    )
    price = g["net_price_f"].median()
    lo, hi = overall["net_price_f"].quantile([0.33, 0.67])
    cost = "low cost" if price < lo else "high cost" if price > hi else "mid cost"
    return f"{size} {sector}, {sel}, {cost}"


def fit_peer_groups(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (per-school group, group profiles, k-selection table)."""
    X = StandardScaler().fit_transform(df[CLUSTER_FEATURES])
    sample = min(len(X), 3000)

    scores = []
    for k in config.CLUSTER_K_RANGE:
        if k >= len(X):
            break
        km = KMeans(n_clusters=k, n_init=10, random_state=config.RANDOM_STATE).fit(X)
        s = silhouette_score(X, km.labels_, sample_size=sample, random_state=config.RANDOM_STATE)
        scores.append({"k": k, "silhouette": round(float(s), 4)})
    selection = pd.DataFrame(scores)
    best_k = int(selection.loc[selection["silhouette"].idxmax(), "k"])
    log.info("peer groups: chose k=%d by silhouette", best_k)

    km = KMeans(n_clusters=best_k, n_init=10, random_state=config.RANDOM_STATE).fit(X)
    work = df.assign(peer_group=km.labels_)

    labels: dict[int, str] = {}
    for gid, g in work.groupby("peer_group"):
        label = _describe_group(g, work)
        if label in labels.values():
            label = f"{label} ({gid + 1})"
        labels[gid] = label
    work["peer_group_label"] = work["peer_group"].map(labels)

    profile = (
        work.groupby(["peer_group", "peer_group_label"])
        .agg(
            n_schools=("unitid", "size"),
            median_enrollment=("enrollment", "median"),
            median_admission_rate=("admission_rate_f", "median"),
            median_net_price=("net_price_f", "median"),
            median_pell_rate=("pell_rate_f", "median"),
            median_grad_rate=("grad_rate_f", "median"),
            median_earnings_10yr_adj=("earnings_10yr_adj", "median"),
            pct_hbcu=("is_hbcu", "mean"),
        )
        .reset_index()
    )
    return work[["unitid", "peer_group", "peer_group_label"]], profile, selection


# --- Orchestration -----------------------------------------------------------------


def run_models(db_path: Path = config.DB_PATH) -> dict[str, object]:
    df = prepare_features(load_mart(db_path))
    if len(df) < 30:
        raise ValueError(f"Only {len(df)} schools with earnings; need at least 30 to model")

    va, coefs, fits = fit_value_added(df)
    groups, profile, selection = fit_peer_groups(df)

    with duckdb.connect(str(db_path)) as con:
        for name, frame in {
            "model_value_added": va,
            "model_coefficients": coefs,
            "model_fit": fits,
            "model_peer_groups": groups,
            "model_peer_group_profile": profile,
            "model_cluster_selection": selection,
        }.items():
            con.register("_frame", frame)
            con.execute(f"create or replace table {name} as select * from _frame")
            con.unregister("_frame")

    gap = hbcu_gap(coefs)
    return {
        "schools_modeled": len(df),
        "value_added_r2": round(float(fits.loc[fits.model == "value_added", "r2"].iat[0]), 3),
        "peer_groups": int(selection.loc[selection["silhouette"].idxmax(), "k"]),
        "hbcu_gap": gap,
    }
