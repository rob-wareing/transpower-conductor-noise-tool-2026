import pytest

from transpower_conductor_noise_tool_2026.backend.ingestion import nw_client
from transpower_conductor_noise_tool_2026.backend.ingestion.nw_client import (
    LoginError,
    NoiseAndWeatherClient,
    ResponseError,
)


class FakeResponse:
    def __init__(self, status_code, json_data=None, reason=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.reason = reason

    def json(self):
        return self._json_data


def _client():
    return NoiseAndWeatherClient(
        base_url="https://fake-nw-api.test/v1", username="user", password="pass"
    )


def test_authenticate_sets_token(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )

    client = _client()
    token = client.authenticate()

    assert token == "abc123"
    assert client._token == "abc123"


def test_authenticate_raises_login_error_on_failure(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(401, reason="bad credentials")
    )

    with pytest.raises(LoginError):
        _client().authenticate()


def test_authenticate_requires_credentials():
    client = NoiseAndWeatherClient(base_url="https://fake-nw-api.test/v1")

    with pytest.raises(LoginError):
        client.authenticate()


def test_sites_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )
    monkeypatch.setattr(
        nw_client.requests,
        "get",
        lambda *a, **kw: FakeResponse(
            200, {"sites": [{"noise_site_id": 51, "site_id": 1}]}
        ),
    )

    sites = _client().sites()

    assert sites == [{"noise_site_id": 51, "site_id": 1}]


def test_sites_raises_response_error_on_failure(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )
    monkeypatch.setattr(
        nw_client.requests, "get", lambda *a, **kw: FakeResponse(500, reason="server error")
    )

    with pytest.raises(ResponseError):
        _client().sites()


def _event(date_time_ms, noise_site_id=51, **overrides):
    noise_data = {
        "date_time": date_time_ms,
        "Leq": 50.0,
        "L90": 48.0,
        "80Hz": 30.0,
        "100Hz": 35.0,
        "125Hz": 31.0,
        "160Hz": 28.0,
        "200Hz": 33.0,
        "250Hz": 29.0,
        "Wind": 1.0,
        "Dir": 180,
        "Rain": 0.0,
    }
    noise_data.update(overrides)
    return {"noise_data": noise_data}


def test_events_paginates_until_has_more_is_false(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )
    monkeypatch.setattr(nw_client, "_throttle", lambda t0: t0)

    pages = [
        {"events": [_event(1735689600000)], "meta": {"total_count": 2, "has_more": True}},
        {"events": [_event(1735693200000)], "meta": {"total_count": 2, "has_more": False}},
    ]
    calls = iter(pages)
    monkeypatch.setattr(nw_client.requests, "get", lambda *a, **kw: FakeResponse(200, next(calls)))

    client = _client()
    df = client.events(site_id=1, start_timestamp=0, end_timestamp=1)

    assert len(df) == 2


def test_events_returns_none_when_no_events(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )
    monkeypatch.setattr(
        nw_client.requests,
        "get",
        lambda *a, **kw: FakeResponse(200, {"events": [], "meta": {"total_count": 0, "has_more": False}}),
    )

    assert _client().events(site_id=1, start_timestamp=0, end_timestamp=1) is None


def test_events_page_reauthenticates_on_401(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )

    responses = iter(
        [
            FakeResponse(401, reason="expired"),
            FakeResponse(200, {"events": [_event(1735689600000)], "meta": {"total_count": 1, "has_more": False}}),
        ]
    )
    monkeypatch.setattr(nw_client.requests, "get", lambda *a, **kw: next(responses))

    df = _client().events(site_id=1, start_timestamp=0, end_timestamp=1)

    assert len(df) == 1


def test_collect_events_stamps_noise_site_id(monkeypatch):
    monkeypatch.setattr(
        nw_client.requests, "post", lambda *a, **kw: FakeResponse(200, {"token": "abc123"})
    )
    monkeypatch.setattr(
        nw_client.requests,
        "get",
        lambda *a, **kw: FakeResponse(
            200, {"events": [_event(1735689600000)], "meta": {"total_count": 1, "has_more": False}}
        ),
    )

    import datetime

    df = _client().collect_events(
        site_id=1,
        noise_site_id=51,
        period_start=datetime.datetime(2025, 1, 1),
        period_end=datetime.datetime(2025, 1, 2),
    )

    assert (df["noise_site_id"] == 51).all()
