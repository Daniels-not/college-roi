import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from scorecard import config
from scorecard.export import run_export
from scorecard.models import build_controls, prepare_features, run_models
from scorecard.synthetic import load_demo
from scorecard.transform import TransformError, run_transforms


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("demo") / "demo.duckdb"
    load_demo(db, n=600, seed=11)
    run_transforms(db)
    result = run_models(db)
    return db, result


def test_cost_of_living_adjustment(demo_db):
    db, _ = demo_db
    with duckdb.connect(str(db), read_only=True) as con:
        rows = con.execute("""
            select state, earnings_10yr, earnings_10yr_adj, price_index
            from mart_institution_roi where state in ('CA', 'MS') limit 20
        """).df()
        pr = con.execute(
            "select bool_and(not has_price_index) from mart_institution_roi where state = 'PR'"
        ).fetchone()[0]
    expected = (rows["earnings_10yr"] / rows["price_index"]).round(0)
    assert np.allclose(rows["earnings_10yr_adj"], expected)
    assert (
        rows.loc[rows.state == "CA", "earnings_10yr_adj"]
        < rows.loc[rows.state == "CA", "earnings_10yr"]
    ).all()  # expensive state
    assert (
        rows.loc[rows.state == "MS", "earnings_10yr_adj"]
        > rows.loc[rows.state == "MS", "earnings_10yr"]
    ).all()  # cheap state
    assert pr is True  # territories have no BEA index -> flagged, left unadjusted


def test_value_added_outputs(demo_db):
    db, result = demo_db
    assert 0 < result["value_added_r2"] < 1
    with duckdb.connect(str(db), read_only=True) as con:
        va = con.execute("select * from model_value_added").df()
        n_mart = con.execute("select count(*) from mart_institution_roi").fetchone()[0]
    assert len(va) == n_mart
    assert va["value_added_rank"].min() == 1
    top = va.sort_values("value_added_rank").iloc[0]
    assert top["value_added_pct"] == va["value_added_pct"].max()
    # OLS residuals (with an intercept) average ~0 on the log scale; the stored
    # values are rounded to 4 decimals, hence the tolerance.
    assert abs(np.log1p(va["value_added_pct"]).mean()) < 1e-4


def test_hbcu_models_present(demo_db):
    db, result = demo_db
    gap = result["hbcu_gap"]
    assert set(gap["model"]) == {"hbcu_raw", "hbcu_controlled"}
    assert (gap["ci_low"] <= gap["coef"]).all() and (gap["coef"] <= gap["ci_high"]).all()


def test_peer_groups(demo_db):
    db, result = demo_db
    with duckdb.connect(str(db), read_only=True) as con:
        groups = con.execute("select * from model_peer_groups").df()
        sel = con.execute("select * from model_cluster_selection").df()
        prof = con.execute("select * from model_peer_group_profile").df()
    assert groups["peer_group"].nunique() == result["peer_groups"]
    assert result["peer_groups"] == sel.loc[sel.silhouette.idxmax(), "k"]
    assert prof["peer_group_label"].is_unique
    assert prof["n_schools"].sum() == len(groups)


def test_export_writes_files_and_metadata(demo_db, tmp_path):
    db, _ = demo_db
    meta = run_export(db, tmp_path)
    assert meta["source"] == "demo"
    assert json.loads((tmp_path / "metadata.json").read_text())["source"] == "demo"
    schools = pd.read_parquet(tmp_path / "schools.parquet")
    assert {"value_added_pct", "peer_group_label", "earnings_10yr_adj"} <= set(schools.columns)
    for f in ["schools", "model_coefficients", "peer_group_profile", "hbcu_summary"]:
        assert (tmp_path / "tableau" / f"{f}.csv").exists()


def test_build_controls_drops_constant_terms():
    df = pd.DataFrame(
        {
            "sat_z": [0.1, 0.2, 0.3],
            "sat_missing": [0, 0, 0],
            "admission_rate_f": [0.5, 0.6, 0.7],
            "admission_missing": [0, 1, 0],
            "pell_rate_f": [0.3, 0.4, 0.5],
            "log_enrollment": [7, 8, 9],
            "ownership": ["Public"] * 3,
            "region_id": [1, 2, 3],
        }
    )
    controls = build_controls(df)
    assert "sat_missing" not in controls
    assert "C(ownership)" not in controls
    assert "admission_missing" in controls and "C(region_id)" in controls


def test_prepare_features_imputes_and_flags():
    df = pd.DataFrame(
        {
            "unitid": [1, 2, 3],
            "earnings_10yr_adj": [40000, 50000, 60000],
            "enrollment": [1000, 2000, 3000],
            "ownership": ["Public"] * 3,
            "is_hbcu": [True, False, False],
            "region_id": [1, None, 2],
            "sat_avg": [1000, None, 1200],
            "admission_rate": [0.5, 0.6, None],
            "pell_rate": [0.3, 0.4, 0.5],
            "net_price": [10000, None, 20000],
            "grad_rate": [0.5, 0.6, 0.7],
        }
    )
    out = prepare_features(df)
    assert out["sat_missing"].tolist() == [0, 1, 0]
    assert out.loc[1, "sat_f"] == 1100
    assert out.loc[1, "region_id"] == -1
    assert out["net_price_f"].notna().all()


def test_dbt_data_tests_catch_bad_data(tmp_path):
    db = tmp_path / "bad.duckdb"
    load_demo(db, n=50)
    with duckdb.connect(str(db)) as con:
        con.execute("update raw_institutions set admission_rate = 1.7 where unitid = 900001")
    with pytest.raises(TransformError):
        run_transforms(db)


def test_demo_paths_are_isolated_from_real_paths():
    assert config.DEMO_DB_PATH != config.DB_PATH
    assert config.DEMO_EXPORT_DIR != config.EXPORT_DIR
