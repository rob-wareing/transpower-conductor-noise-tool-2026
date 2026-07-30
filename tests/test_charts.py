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


def test_charts_endpoint_rejects_out_of_range_interval_weeks(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"interval_weeks": 5})

    assert response.status_code == 400


def _noise_chart_point_count(response):
    payload = response.get_json()
    traces = payload["noise_chart"]["data"]
    assert len(traces) == 1
    return len(traces[0]["x"])


def test_charts_endpoint_buckets_readings_into_fewer_points_than_raw_readings(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch)

    # Site 51 ("Demo Site") has 50 daily readings and no HistoricalResult rows,
    # so its noise-chart trace should be purely the bucketed current-data line.
    response = client.post(
        "/api/charts", json={"noise_site_id": [51], "interval_weeks": 2}
    )

    assert response.status_code == 200
    assert 0 < _noise_chart_point_count(response) < 50


def test_charts_endpoint_wider_interval_produces_fewer_or_equal_buckets(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    one_week = client.post("/api/charts", json={"noise_site_id": [51], "interval_weeks": 1})
    four_weeks = client.post("/api/charts", json={"noise_site_id": [51], "interval_weeks": 4})

    assert _noise_chart_point_count(four_weeks) <= _noise_chart_point_count(one_week)


def test_charts_endpoint_overlays_historical_results_before_cutover(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # Site 115 has both ProcessedReading rows (2025) and HistoricalResult rows
    # (up to 2019) - the historical points should appear alongside the bucketed
    # current-data points, since none of the current data predates the cutover.
    without_historical = client.post("/api/charts", json={"noise_site_id": [999999]})
    with_historical = client.post("/api/charts", json={"noise_site_id": [115]})

    assert without_historical.status_code == 200
    assert with_historical.status_code == 200

    payload = with_historical.get_json()["noise_chart"]["data"][0]
    dates = payload["x"]
    assert any(str(d).startswith("2019") or str(d).startswith("2016") for d in dates)
    assert any(str(d).startswith("2025") for d in dates)


def test_charts_endpoint_excludes_historical_results_for_dry_condition(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts", json={"noise_site_id": [115], "condition": "dry"}
    )

    assert response.status_code == 200
    traces = response.get_json()["noise_chart"]["data"]
    if traces:
        dates = traces[0]["x"]
        assert not any(str(d).startswith("2019") or str(d).startswith("2016") for d in dates)
