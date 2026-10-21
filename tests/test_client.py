import pytest

from scorecard.client import ScorecardClient, ScorecardError

from conftest import FakeSession, make_institution


def test_paginates_until_total_reached():
    session = FakeSession([make_institution(i) for i in range(250)])
    client = ScorecardClient(api_key="k", session=session, page_delay=0)
    results = list(client.iter_results(["id"], {}))
    assert len(results) == 250
    assert [c["page"] for c in session.calls] == [0, 1, 2]
    assert all(c["per_page"] == 100 for c in session.calls)


def test_max_pages_stops_early():
    session = FakeSession([make_institution(i) for i in range(250)])
    client = ScorecardClient(api_key="k", session=session, page_delay=0)
    assert len(list(client.iter_results(["id"], {}, max_pages=1))) == 100


def test_filters_and_fields_are_sent():
    session = FakeSession([make_institution(0)])
    client = ScorecardClient(api_key="secret", session=session, page_delay=0)
    list(client.iter_results(["id", "school.name"], {"school.state": "AL"}))
    params = session.calls[0]
    assert params["fields"] == "id,school.name"
    assert params["school.state"] == "AL"
    assert params["api_key"] == "secret"


def test_http_error_raises_without_leaking_key():
    session = FakeSession([make_institution(0)], status_code=403)
    client = ScorecardClient(api_key="secret", session=session, page_delay=0)
    with pytest.raises(ScorecardError) as exc:
        list(client.iter_results(["id"], {}))
    assert "403" in str(exc.value)
    assert "secret" not in str(exc.value)


def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr("scorecard.config.API_KEY", "")
    with pytest.raises(ScorecardError, match="Missing API key"):
        ScorecardClient()


def test_empty_result_set():
    client = ScorecardClient(api_key="k", session=FakeSession([]), page_delay=0)
    assert list(client.iter_results(["id"], {})) == []
