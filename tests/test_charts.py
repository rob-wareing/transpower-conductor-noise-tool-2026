from transpower_conductor_noise_tool_2026.backend.app import create_app


def _make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app.test_client()


def test_charts_endpoint_returns_both_figures(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert "data" in payload["noise_chart"]
    assert "layout" in payload["noise_chart"]
    assert "data" in payload["timeline_chart"]
    assert "layout" in payload["timeline_chart"]
    assert len(payload["timeline_chart"]["data"]) > 0


def test_charts_endpoint_filters_by_site(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    all_sites_response = client.post("/api/charts", json={})
    single_site_response = client.post("/api/charts", json={"noise_site_id": [51]})

    all_sites_bars = len(all_sites_response.get_json()["timeline_chart"]["data"])
    single_site_bars = len(single_site_response.get_json()["timeline_chart"]["data"])

    assert single_site_bars == 1
    assert single_site_bars < all_sites_bars


def test_charts_endpoint_with_no_matching_data_returns_empty_figures(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"noise_site_id": [999999]})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["noise_chart"]["data"] == []
    assert payload["timeline_chart"]["data"] == []


def test_charts_endpoint_rejects_invalid_payload(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"start_date": "not-a-date"})

    assert response.status_code == 400
