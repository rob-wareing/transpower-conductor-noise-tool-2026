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


def test_charts_endpoint_returns_noise_chart(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert "data" in payload["noise_chart"]
    assert "layout" in payload["noise_chart"]
    assert "timeline_chart" not in payload  # moved to GET /api/charts/timeline


def test_charts_endpoint_with_no_matching_data_returns_empty_figure(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post("/api/charts", json={"noise_site_id": [999999]})

    assert response.status_code == 200
    assert response.get_json()["noise_chart"]["data"] == []


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
    assert response.get_json()["noise_chart"]["data"] == []


# --- GET /api/charts/timeline (decoupled from every Charts tab option) -----


def test_charts_timeline_endpoint_returns_empty_when_no_availability_data(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/charts/timeline")

    assert response.status_code == 200
    assert response.get_json()["timeline_chart"]["data"] == []


def test_charts_timeline_endpoint_returns_a_bar_per_precomputed_site(tmp_path, monkeypatch):
    from datetime import datetime

    from transpower_conductor_noise_tool_2026.backend.persistence.models.reading_availability import (
        ReadingAvailability,
    )

    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            ReadingAvailability(
                noise_site_id=51,
                min_datetime=datetime(2018, 1, 1),
                max_datetime=datetime(2025, 1, 1),
                row_count=100,
                computed_at=datetime(2026, 8, 22),
            )
        )
        db.session.commit()

    response = client.get("/api/charts/timeline")

    assert response.status_code == 200
    payload = response.get_json()["timeline_chart"]
    assert len(payload["data"]) == 1
    assert payload["data"][0]["x"][0] == "2018-01-01T00:00:00"


def test_charts_timeline_endpoint_excludes_ignored_sites(tmp_path, monkeypatch):
    from datetime import datetime

    from transpower_conductor_noise_tool_2026.backend.persistence.models.reading_availability import (
        ReadingAvailability,
    )

    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        site = Site.query.filter_by(noise_site_id=51).first()
        site.is_ignored = True
        db.session.add(
            ReadingAvailability(
                noise_site_id=51,
                min_datetime=datetime(2018, 1, 1),
                max_datetime=datetime(2025, 1, 1),
                row_count=100,
                computed_at=datetime(2026, 8, 22),
            )
        )
        db.session.commit()

    response = client.get("/api/charts/timeline")

    assert response.status_code == 200
    assert response.get_json()["timeline_chart"]["data"] == []


def test_charts_timeline_endpoint_unaffected_by_query_params(tmp_path, monkeypatch):
    # No filters are accepted at all - a plain GET is the only shape. This
    # confirms the endpoint doesn't silently read/act on stray query params
    # a stale client might still send.
    from datetime import datetime

    from transpower_conductor_noise_tool_2026.backend.persistence.models.reading_availability import (
        ReadingAvailability,
    )

    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            ReadingAvailability(
                noise_site_id=51,
                min_datetime=datetime(2018, 1, 1),
                max_datetime=datetime(2025, 1, 1),
                row_count=100,
                computed_at=datetime(2026, 8, 22),
            )
        )
        db.session.commit()

    plain = client.get("/api/charts/timeline").get_json()
    with_params = client.get("/api/charts/timeline?noise_site_id=999999&start_date=2025-01-01").get_json()

    assert plain == with_params


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


def test_charts_endpoint_includes_pre_2020_processed_readings_by_default(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        from datetime import datetime

        from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
            ProcessedReading,
        )

        # Site 137 does carry AUTO_SEED_DATA baseline rows (all dated 2025,
        # like every seedable site's - see CLAUDE.md's gotcha), but none of
        # them predate 2020, so this added row is unambiguously the only
        # 2018-dated one.
        db.session.add(
            ProcessedReading(
                noise_site_id=137,
                datetime=datetime(2018, 6, 1),
                l90=40.0,
                tone_100hz=1.0,
                tone_200hz=1.0,
                rain1=0.0,
                rain2=0.0,
                is_wet=False,
                include=True,
            )
        )
        db.session.commit()

    response = client.post("/api/charts/table", json={"noise_site_id": [137]})

    assert response.status_code == 200
    dates = [item["datetime"] for item in response.get_json()["items"]]
    assert any(str(d).startswith("2018") for d in dates)


def test_charts_endpoint_uses_its_own_much_higher_per_site_cap(tmp_path, monkeypatch):
    from datetime import datetime

    from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
        ProcessedReading,
    )

    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        # Every seedable site (data/site.csv) already carries some baseline
        # processed_reading rows (see AUTO_SEED_DATA gotcha - not just
        # 51/115), all dated 2025 - so these 10 rows are dated 2030,
        # unambiguously the most recent regardless of whatever baseline data
        # site 137 also has.
        for day in range(1, 11):
            db.session.add(
                ProcessedReading(
                    noise_site_id=137,
                    datetime=datetime(2030, 1, day),
                    l90=40.0,
                    tone_100hz=1.0,
                    tone_200hz=1.0,
                    rain1=0.0,
                    rain2=0.0,
                    is_wet=False,
                    include=True,
                )
            )
        db.session.commit()

    # Charts' own cap (CHARTS_PER_SITE_LIMIT, far above these 10 rows plus
    # whatever baseline data exists) keeps every one of these 10 rows.
    response = client.post("/api/charts/table", json={"noise_site_id": [137]})
    dates = {item["datetime"] for item in response.get_json()["items"]}
    assert {f"2030-01-{day:02d}T00:00:00" for day in range(1, 11)} <= dates

    # Configuring Charts' cap down to less than the row count truncates to
    # that many most-recent rows - proving chart_service reads
    # Settings.CHARTS_PER_SITE_LIMIT (not the repository's own
    # PER_SITE_READING_LIMIT-derived default) on every request, not just once
    # at import time.
    from transpower_conductor_noise_tool_2026.backend.config import Settings

    monkeypatch.setattr(Settings, "CHARTS_PER_SITE_LIMIT", 3)
    capped_response = client.post("/api/charts/table", json={"noise_site_id": [137]})
    capped_items = capped_response.get_json()["items"]
    assert len(capped_items) == 3
    assert {item["datetime"] for item in capped_items} == {
        "2030-01-08T00:00:00",
        "2030-01-09T00:00:00",
        "2030-01-10T00:00:00",
    }


def test_charts_endpoint_hides_historical_results_by_default(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # Site 115 has HistoricalResult rows up to 2019 - show_historical defaults
    # to False, so a plain request must never include them.
    response = client.post("/api/charts", json={"noise_site_id": [115]})

    assert response.status_code == 200
    payload = response.get_json()["noise_chart"]["data"][0]
    dates = payload["x"]
    assert not any(str(d).startswith("2019") or str(d).startswith("2016") for d in dates)
    assert any(str(d).startswith("2025") for d in dates)


def test_charts_endpoint_overlays_historical_results_before_cutover(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    # Site 115 has both ProcessedReading rows (2025) and HistoricalResult rows
    # (up to 2019) - the historical points should appear alongside the bucketed
    # current-data points, since none of the current data predates the cutover.
    # They render as two separate traces (the historical one at reduced
    # opacity - see the historical/current trace-splitting in
    # chart_service._build_noise_chart), sharing one legend entry.
    without_historical = client.post(
        "/api/charts", json={"noise_site_id": [999999], "show_historical": True}
    )
    with_historical = client.post(
        "/api/charts", json={"noise_site_id": [115], "show_historical": True}
    )

    assert without_historical.status_code == 200
    assert with_historical.status_code == 200

    traces = with_historical.get_json()["noise_chart"]["data"]
    assert len(traces) == 2
    all_dates = [d for trace in traces for d in trace["x"]]
    assert any(str(d).startswith("2019") or str(d).startswith("2016") for d in all_dates)
    assert any(str(d).startswith("2025") for d in all_dates)

    historical_trace, current_trace = traces
    assert historical_trace.get("opacity") == 0.5
    assert current_trace.get("opacity") in (None, 1.0)
    assert historical_trace["legendgroup"] == current_trace["legendgroup"]
    assert historical_trace["showlegend"] is True
    assert current_trace["showlegend"] is False


def test_charts_endpoint_historical_trace_defaults_to_current_traces_own_color(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch)

    # Site 115's historical_line_color is unset (the AUTO_SEED_DATA baseline
    # never sets it) - its historical trace should fall back to reusing the
    # same color its current-data trace uses, not some other color.
    response = client.post(
        "/api/charts", json={"noise_site_id": [115], "show_historical": True}
    )

    assert response.status_code == 200
    historical_trace, current_trace = response.get_json()["noise_chart"]["data"]
    assert historical_trace["line"]["color"] == current_trace["line"]["color"]


def test_charts_endpoint_historical_trace_uses_sites_historical_line_color_override(
    tmp_path, monkeypatch
):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        site = Site.query.filter_by(noise_site_id=115).first()
        site.historical_line_color = "#ff00ff"
        db.session.commit()

    response = client.post(
        "/api/charts", json={"noise_site_id": [115], "show_historical": True}
    )

    assert response.status_code == 200
    historical_trace, current_trace = response.get_json()["noise_chart"]["data"]
    assert historical_trace["line"]["color"] == "#ff00ff"
    assert current_trace["line"]["color"] != "#ff00ff"


def test_charts_endpoint_applies_reconductoring_linestyle_from_its_date_onward(
    tmp_path, monkeypatch
):
    from datetime import date as date_

    from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
        Reconductoring,
    )

    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        # Site 51's 50 seeded daily readings span 2025-02-17 to 2025-04-07
        # (see test_charts_endpoint_conductor_and_treatment_filter_splits_trace_name) -
        # this cutover sits roughly in the middle, giving both a solid
        # (pre-cutover) and a dash (post-cutover) segment.
        db.session.add(
            Reconductoring(
                noise_site_id=51,
                reconductoring_date=date_(2025, 3, 1),
                plot_linestyle="dash",
            )
        )
        db.session.commit()

    response = client.post("/api/charts", json={"noise_site_id": [51]})

    assert response.status_code == 200
    traces = response.get_json()["noise_chart"]["data"]
    dash_values = {trace["line"]["dash"] for trace in traces}
    assert dash_values == {"solid", "dash"}


def test_charts_endpoint_excludes_historical_results_for_dry_condition(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/charts",
        json={"noise_site_id": [115], "condition": "dry", "show_historical": True},
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
