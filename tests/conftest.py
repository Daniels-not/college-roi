from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scorecard import config  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    """Serves canned pages; routes program requests by the `fields` param."""

    def __init__(
        self, institutions: list[dict], programs: list[dict] | None = None, status_code: int = 200
    ) -> None:
        self.institutions = institutions
        self.programs = programs or []
        self.status_code = status_code
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append(params)
        data = self.programs if config.PROGRAMS_FIELD in params["fields"] else self.institutions
        page, per = int(params["page"]), int(params["per_page"])
        chunk = data[page * per : (page + 1) * per]
        return FakeResponse(
            {"metadata": {"total": len(data), "page": page, "per_page": per}, "results": chunk},
            status_code=self.status_code,
        )


def make_institution(i: int, **overrides: Any) -> dict[str, Any]:
    rec = {
        "id": 100000 + i,
        "school.name": f"School {i}",
        "school.city": "Huntsville",
        "school.state": "AL",
        "school.region_id": 5,
        "school.locale": 12,
        "school.ownership": 1 + (i % 2),
        "school.minority_serving.historically_black": 1 if i % 10 == 0 else 0,
        "location.lat": 34.7,
        "location.lon": -86.6,
        "latest.student.size": 1000 + i,
        "latest.admissions.admission_rate.overall": 0.6,
        "latest.admissions.sat_scores.average.overall": 1100,
        "latest.cost.tuition.in_state": 10000,
        "latest.cost.tuition.out_of_state": 25000,
        "latest.cost.avg_net_price.public": 15000 if i % 2 == 0 else None,
        "latest.cost.avg_net_price.private": None if i % 2 == 0 else 22000,
        "latest.aid.pell_grant_rate": 0.4,
        "latest.aid.federal_loan_rate": 0.5,
        "latest.aid.median_debt.completers.overall": 25000,
        "latest.completion.completion_rate_4yr_150nt": 0.55,
        "latest.student.retention_rate.four_year.full_time": 0.75,
        "latest.earnings.6_yrs_after_entry.median": 38000,
        "latest.earnings.10_yrs_after_entry.median": 50000,
    }
    rec.update(overrides)
    return rec


def make_program_record(i: int, n_programs: int = 2) -> dict[str, Any]:
    return {
        "id": 100000 + i,
        "school.name": f"School {i}",
        config.PROGRAMS_FIELD: [
            {
                "code": f"110{p}",
                "title": f"Program {p}",
                "credential": {"level": 3, "title": "Bachelor's Degree"},
                "earnings": {"4_yr": {"overall_median_earnings": 55000 + p}},
            }
            for p in range(n_programs)
        ],
    }


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.duckdb"
