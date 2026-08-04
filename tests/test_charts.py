from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.site import Site


def _make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app.test_client()


def _make_app_and_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app, app.test_client()


def _login(client, email="demo@transpower.example", password="demo-password"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


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


def test_charts_endpoint_excludes_ignored_site_even_when_explicitly_requested(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        site = Site.query.filter_by(noise_site_id=51).first()
        site.is_ignored = True
        db.session.commit()

    # Site 51 has seeded demo readings and would normally show data, but an
    # ignored site's readings must never be queried, even if a stale client
    # explicitly asks for its id by name.
    response = client.post("/api/charts", json={"noise_site_id": [51]})

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


def test_charts_endpoint_conductor_and_treatment_filter_splits_trace_name(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # Site 51 ("Demo Site") has a single Reconductoring event dated 2024-11-15
    # ("Standard conductor (standard grease)"), and all of its 50 readings
    # postdate that event, so they all get stamped with it.
    response = client.post(
        "/api/charts",
        json={
            "noise_site_id": [51],
            "conductor_and_treatment": ["Standard conductor (standard grease)"],
        },
    )

    assert response.status_code == 200
    traces = response.get_json()["noise_chart"]["data"]
    assert len(traces) == 1
    assert "Standard conductor (standard grease)" in traces[0]["name"]


def test_charts_endpoint_conductor_and_treatment_filter_excludes_unmatched_sites(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch)

    # Site 87 ("Portable Logger 3") has no Reconductoring events at all, so
    # every one of its readings stays unstamped ("") and gets filtered out.
    response = client.post(
        "/api/charts",
        json={
            "noise_site_id": [87],
            "conductor_and_treatment": ["Standard conductor (standard grease)"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["noise_chart"]["data"] == []


def test_charts_endpoint_grease_filter_matches_conductor_and_treatment_filter(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"noise_site_id": [51], "grease": ["standard"]})

    assert response.status_code == 200
    traces = response.get_json()["noise_chart"]["data"]
    assert len(traces) == 1
    assert "Standard conductor (standard grease)" in traces[0]["name"]


def test_charts_endpoint_days_since_conductoring_guard_returns_empty_without_a_filter(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts", json={"noise_site_id": [51], "plot_by": "days_since_conductoring"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["noise_chart"]["data"] == []
    assert "conductor" in payload["noise_chart"]["layout"]["title"]["text"].lower()


def test_charts_endpoint_days_since_conductoring_plots_numeric_x_axis_with_filter(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts",
        json={
            "noise_site_id": [51],
            "plot_by": "days_since_conductoring",
            "conductor_and_treatment": ["Standard conductor (standard grease)"],
        },
    )

    assert response.status_code == 200
    traces = response.get_json()["noise_chart"]["data"]
    assert len(traces) == 1
    assert all(isinstance(x, (int, float)) for x in traces[0]["x"])


def test_charts_endpoint_rejects_invalid_plot_by(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"plot_by": "not-a-real-mode"})

    assert response.status_code == 400


def test_charts_endpoint_defaults_to_15_minute_readings(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # All seeded demo ProcessedReading rows are 15-minute measurements, so the
    # default measurement_duration filter (15) should behave identically to
    # not filtering at all.
    response = client.post("/api/charts", json={"noise_site_id": [51]})

    assert response.status_code == 200
    assert _noise_chart_point_count(response) > 0


def test_charts_endpoint_1_minute_duration_returns_no_data(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # No seeded data is a 1-minute measurement yet, so this filter should
    # exclude every reading.
    response = client.post(
        "/api/charts", json={"noise_site_id": [51], "measurement_duration": 1}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["noise_chart"]["data"] == []


def test_charts_endpoint_rejects_invalid_measurement_duration(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"measurement_duration": 5})

    assert response.status_code == 400


def test_charts_table_endpoint_1_minute_duration_returns_no_rows(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts/table", json={"noise_site_id": [51], "measurement_duration": 1}
    )

    assert response.status_code == 200
    assert response.get_json()["items"] == []


def test_charts_endpoint_defaults_to_original_detection_logic(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # All seeded demo ProcessedReading rows are tagged detection_logic="original"
    # (the model's own default), so the default filter should behave identically
    # to not filtering at all.
    response = client.post("/api/charts", json={"noise_site_id": [51]})

    assert response.status_code == 200
    assert _noise_chart_point_count(response) > 0


def test_charts_endpoint_updated_2026_detection_logic_returns_no_data(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # No seeded data has been processed through the new detection logic yet
    # (that only happens via real ingestion or the backfill script), so this
    # filter should exclude every reading.
    response = client.post(
        "/api/charts", json={"noise_site_id": [51], "detection_logic": "updated_2026"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["noise_chart"]["data"] == []


def test_charts_endpoint_rejects_invalid_detection_logic(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"detection_logic": "not-a-real-logic"})

    assert response.status_code == 400


def test_charts_table_endpoint_updated_2026_detection_logic_returns_no_rows(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts/table", json={"noise_site_id": [51], "detection_logic": "updated_2026"}
    )

    assert response.status_code == 200
    assert response.get_json()["items"] == []


def test_charts_table_endpoint_returns_augmented_rows(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts/table", json={"noise_site_id": [51]})

    assert response.status_code == 200
    items = response.get_json()["items"]
    assert len(items) == 50
    assert all(item["conductor_and_treatment"] == "Standard conductor (standard grease)" for item in items)
    assert all(item["days_since_conductoring"] is not None for item in items)
    assert {"id", "noise_site_id", "datetime", "leq_adj", "is_wet", "include"} <= set(items[0].keys())


def test_charts_table_endpoint_respects_conductor_filter(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts/table",
        json={
            "noise_site_id": [87],
            "conductor_and_treatment": ["Standard conductor (standard grease)"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["items"] == []


def test_update_processed_reading_requires_authentication(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.patch("/api/processed-readings/1", json={"include": False})

    assert response.status_code == 401


def test_update_processed_reading_requires_write_access(tmp_path, monkeypatch):
    from transpower_conductor_noise_tool_2026.backend.domain.auth_service import create_user

    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        create_user("Read Only", "readonly@transpower.example", "password", write_access=False)
    _login(client, "readonly@transpower.example", "password")

    response = client.patch("/api/processed-readings/1", json={"include": False})

    assert response.status_code == 403


def test_update_processed_reading_with_write_access_persists(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _login(client)

    table_response = client.post("/api/charts/table", json={"noise_site_id": [51]})
    reading_id = table_response.get_json()["items"][0]["id"]

    response = client.patch(f"/api/processed-readings/{reading_id}", json={"include": False})

    assert response.status_code == 200

    with app.app_context():
        from transpower_conductor_noise_tool_2026.backend.extensions import db
        from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
            ProcessedReading,
        )

        reading = db.session.get(ProcessedReading, reading_id)
        assert reading.include is False


def test_update_processed_reading_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/processed-readings/999999", json={"include": False})

    assert response.status_code == 404


def test_charts_table_endpoint_excludes_readings_during_known_outages(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # Site 115 has a seeded Outage from 2025-03-05T00:00 to 2025-03-06T00:00
    # (exclusive start, inclusive end) and a daily reading at exactly
    # 2025-03-06T00:00 - that one reading should be excluded from the raw
    # table entirely, while the boundary reading at 2025-03-05T00:00 (not
    # strictly *after* the outage start) is kept.
    response = client.post("/api/charts/table", json={"noise_site_id": [115]})

    assert response.status_code == 200
    items = response.get_json()["items"]
    dates = {item["datetime"] for item in items}
    assert "2025-03-06T00:00:00" not in dates
    assert "2025-03-05T00:00:00" in dates


def test_charts_table_endpoint_outage_exclusion_is_scoped_to_its_own_site(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # Site 51 has no reading inside its own seeded Outage window (which
    # predates its reading history), so its row count should be unaffected -
    # this guards against a sitewide-instead-of-windowed exclusion bug.
    response = client.post("/api/charts/table", json={"noise_site_id": [51]})

    assert response.status_code == 200
    assert len(response.get_json()["items"]) == 50
