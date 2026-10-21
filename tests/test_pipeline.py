import duckdb
import pytest

from scorecard import config
from scorecard.client import ScorecardClient
from scorecard.ingest import institutions_to_frame, programs_to_frame, run_ingest
from scorecard.transform import data_quality_report, run_transforms

from conftest import FakeSession, make_institution, make_program_record


def test_institutions_frame_renames_and_fills_missing_columns():
    rec = make_institution(1)
    del rec["latest.admissions.sat_scores.average.overall"]
    df = institutions_to_frame([rec, rec])  # duplicate on purpose
    assert list(df.columns) == list(config.INSTITUTION_FIELDS.values())
    assert len(df) == 1
    assert df["sat_avg"].isna().all()


def test_programs_frame_explodes_nested_array():
    df = programs_to_frame([make_program_record(1, 3), make_program_record(2, 2)])
    assert len(df) == 5
    assert {
        "unitid",
        "school_name",
        "code",
        "credential__level",
        "earnings__4_yr__overall_median_earnings",
    } <= set(df.columns)
    assert df.columns[0] == "unitid"


def test_programs_frame_handles_missing_and_single_dict():
    single = make_program_record(1, 1)
    single[config.PROGRAMS_FIELD] = single[config.PROGRAMS_FIELD][0]
    none = {"id": 5, "school.name": "X", config.PROGRAMS_FIELD: None}
    assert len(programs_to_frame([single, none])) == 1


@pytest.fixture
def built_db(tmp_db, tmp_path):
    insts = [make_institution(i) for i in range(120)]
    insts.append(
        make_institution(999, **{"latest.aid.median_debt.completers.overall": "PrivacySuppressed"})
    )
    insts.append(make_institution(998, **{"latest.earnings.10_yrs_after_entry.median": None}))
    progs = [make_program_record(i) for i in range(120)]
    client = ScorecardClient(api_key="k", session=FakeSession(insts, progs), page_delay=0)
    counts = run_ingest(client, db_path=tmp_db, raw_dir=tmp_path / "raw")
    run_transforms(db_path=tmp_db)
    return tmp_db, counts, tmp_path / "raw"


def test_end_to_end_counts_and_raw_files(built_db):
    db, counts, raw = built_db
    assert counts == {"institutions": 122, "programs": 240}
    assert len(list(raw.glob("institutions_*.jsonl"))) == 1
    assert len(list(raw.glob("programs_*.jsonl"))) == 1


def test_staging_cleans_types(built_db):
    db, _, _ = built_db
    with duckdb.connect(str(db), read_only=True) as con:
        suppressed = con.execute(
            "SELECT median_debt FROM stg_institutions WHERE unitid = 100999"
        ).fetchone()[0]
        owners = {
            r[0] for r in con.execute("SELECT DISTINCT ownership FROM stg_institutions").fetchall()
        }
        null_net = con.execute(
            "SELECT COUNT(*) FROM stg_institutions WHERE net_price IS NULL"
        ).fetchone()[0]
    assert suppressed is None
    assert owners == {"Public", "Private nonprofit"}
    assert null_net == 0  # public/private net price coalesced


def test_mart_metrics(built_db):
    db, _, _ = built_db
    with duckdb.connect(str(db), read_only=True) as con:
        row = con.execute(
            "SELECT debt_to_earnings, payback_years, net_cost_4yr FROM mart_institution_roi "
            "WHERE unitid = 100002"
        ).fetchone()
        n = con.execute("SELECT COUNT(*) FROM mart_institution_roi").fetchone()[0]
        hbcu = con.execute("SELECT group_name, n_schools FROM mart_hbcu_summary").fetchall()
    assert row == (0.5, 5.0, 60000.0)  # 25k / 50k ; 25k / 5k ; 15k * 4
    assert n == 121  # school with no earnings excluded
    assert dict(hbcu)["HBCU"] == 12


def test_quality_report(built_db):
    db, _, _ = built_db
    report = data_quality_report(db_path=db)
    assert report["institutions"] == 122
    assert report["duplicate_unitids"] == 0
    assert report["hbcus"] == 12
