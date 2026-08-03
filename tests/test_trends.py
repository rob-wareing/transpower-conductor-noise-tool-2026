from datetime import date, datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.conductor_summary import (
    ConductorSummary,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.rain_rate_fit import (
    RainRateFit,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)

KNOWN_SITE = 115  # from data/site.csv
OTHER_KNOWN_SITE = 137  # from data/site.csv


def _make_app_and_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app, app.test_client()


def _seed_summary_row(app, **overrides):
    defaults = dict(
        noise_site_id=KNOWN_SITE,
        detection_logic="original",
        measurement_duration_minutes=15,
        l90_mean=40.0, l90_max=48.0, l90_min=35.0, l90_median=41.0, l90_q1=38.0, l90_q3=44.0,
        tone_100hz_mean=1.0, tone_100hz_max=2.0, tone_100hz_min=0.5,
        tone_100hz_median=1.2, tone_100hz_q1=0.8, tone_100hz_q3=1.5,
        tone_200hz_mean=0.9, tone_200hz_max=1.8, tone_200hz_min=0.4,
        tone_200hz_median=1.0, tone_200hz_q1=0.7, tone_200hz_q3=1.3,
        sample_count=23,
        computed_at=datetime(2026, 8, 2, 0, 0, 0),
    )
    defaults.update(overrides)
    with app.app_context():
        db.session.add(ConductorSummary(**defaults))
        db.session.commit()


def test_conductor_summary_endpoint_returns_a_valid_empty_figure_with_no_data(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.post("/api/trends/conductor-summary", json={})

    assert response.status_code == 200
    payload = response.get_json()
    chart = payload["conductor_summary_chart"]
    assert chart["data"] == []
    assert "No conductor summary data" in chart["layout"]["title"]["text"]


def test_conductor_summary_endpoint_returns_a_single_horizontal_box_trace_for_seeded_data(
    tmp_path, monkeypatch
):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _seed_summary_row(app)

    response = client.post(
        "/api/trends/conductor-summary",
        json={"metric": "l90", "detection_logic": "original", "measurement_duration_minutes": 15},
    )

    assert response.status_code == 200
    chart = response.get_json()["conductor_summary_chart"]
    assert len(chart["data"]) == 1
    assert chart["data"][0]["orientation"] == "h"
    assert chart["data"][0]["median"] == [41.0]
    # no Reconductoring row seeded for KNOWN_SITE -> falls into "Unknown"
    assert chart["data"][0]["name"] == "Unknown"


def test_conductor_summary_endpoint_metric_selects_the_right_stats(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _seed_summary_row(app)

    response = client.post("/api/trends/conductor-summary", json={"metric": "tone_100hz"})

    assert response.status_code == 200
    chart = response.get_json()["conductor_summary_chart"]
    assert chart["data"][0]["median"] == [1.2]


def test_conductor_summary_endpoint_rejects_invalid_detection_logic(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.post("/api/trends/conductor-summary", json={"detection_logic": "bogus"})

    assert response.status_code == 400


def test_conductor_summary_endpoint_rejects_invalid_measurement_duration(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/trends/conductor-summary", json={"measurement_duration_minutes": 5}
    )

    assert response.status_code == 400


def test_conductor_summary_endpoint_rejects_invalid_metric(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.post("/api/trends/conductor-summary", json={"metric": "leq"})

    assert response.status_code == 400


def test_conductor_summary_endpoint_filters_by_site(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _seed_summary_row(app, noise_site_id=KNOWN_SITE)
    _seed_summary_row(app, noise_site_id=OTHER_KNOWN_SITE, sample_count=9)

    response = client.post(
        "/api/trends/conductor-summary", json={"noise_site_id": [KNOWN_SITE]}
    )

    assert response.status_code == 200
    chart = response.get_json()["conductor_summary_chart"]
    assert len(chart["data"]) == 1
    assert f"({KNOWN_SITE})" in chart["data"][0]["y"][0]


def _seed_reconductoring_event(app, **overrides):
    defaults = dict(
        noise_site_id=KNOWN_SITE,
        conductor_and_treatment="Zebra emulsified fat drawn",
        reconductoring_date=date(2020, 1, 1),
    )
    defaults.update(overrides)
    with app.app_context():
        db.session.add(Reconductoring(**defaults))
        db.session.commit()


def test_conductor_summary_endpoint_colors_box_by_conductor_type(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _seed_summary_row(app, noise_site_id=KNOWN_SITE)
    # KNOWN_SITE already has a baseline demo Reconductoring row
    # (data/reconductoring.csv, dated 2025-02-01) - this needs a later date to
    # actually be "most recent" and win.
    _seed_reconductoring_event(
        app,
        noise_site_id=KNOWN_SITE,
        conductor_and_treatment="Chukar treated",
        reconductoring_date=date(2026, 1, 1),
    )

    response = client.post("/api/trends/conductor-summary", json={})

    assert response.status_code == 200
    chart = response.get_json()["conductor_summary_chart"]
    assert len(chart["data"]) == 1
    assert chart["data"][0]["name"] == "Chukar"


def _seed_processed_reading(app, **overrides):
    defaults = dict(
        noise_site_id=KNOWN_SITE,
        datetime=datetime(2026, 8, 3, 23, 0, 0),
        l90=40.0,
        tone_100hz=1.0,
        tone_200hz=0.5,
        rain1=2.0,
        rain2=0.0,
        is_wet=True,
        include=True,
        measurement_duration_minutes=15,
        detection_logic="original",
    )
    defaults.update(overrides)
    with app.app_context():
        db.session.add(ProcessedReading(**defaults))
        db.session.commit()


def test_rain_rate_vs_level_endpoint_returns_a_valid_empty_figure_with_no_data(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    # AUTO_SEED_DATA seeds 829 demo ProcessedReading rows, all detection_logic
    # ="original" (the model default) - "updated_2026" has genuinely zero
    # seeded rows, same trick used elsewhere in this suite (test_ingestion_job
    # .py) to get a real, guaranteed-empty baseline.
    response = client.post(
        "/api/trends/rain-rate-vs-level", json={"detection_logic": "updated_2026"}
    )

    assert response.status_code == 200
    chart = response.get_json()["rain_rate_vs_level_chart"]
    assert chart["data"] == []
    assert "No processed reading data" in chart["layout"]["title"]["text"]


def test_rain_rate_vs_level_endpoint_returns_one_trace_per_site(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _seed_processed_reading(app, noise_site_id=KNOWN_SITE, rain1=2.0, l90=40.0)
    _seed_processed_reading(
        app,
        noise_site_id=OTHER_KNOWN_SITE,
        datetime=datetime(2026, 8, 3, 23, 15, 0),
        rain1=1.0,
        l90=38.0,
    )

    # Scoped to exactly these 2 sites - the demo seed also has baseline rows
    # for both (extra points on the same 2 traces, not extra traces), so this
    # still correctly proves "one trace per site" regardless of that baseline.
    response = client.post(
        "/api/trends/rain-rate-vs-level",
        json={"metric": "l90", "noise_site_id": [KNOWN_SITE, OTHER_KNOWN_SITE]},
    )

    assert response.status_code == 200
    chart = response.get_json()["rain_rate_vs_level_chart"]
    assert len(chart["data"]) == 2
    assert chart["data"][0]["mode"] == "markers"


def test_rain_rate_vs_level_endpoint_filters_by_site(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    _seed_processed_reading(app, noise_site_id=KNOWN_SITE)
    _seed_processed_reading(
        app,
        noise_site_id=OTHER_KNOWN_SITE,
        datetime=datetime(2026, 8, 3, 23, 15, 0),
    )

    response = client.post(
        "/api/trends/rain-rate-vs-level", json={"noise_site_id": [KNOWN_SITE]}
    )

    assert response.status_code == 200
    chart = response.get_json()["rain_rate_vs_level_chart"]
    assert len(chart["data"]) == 1


def test_rain_rate_vs_level_endpoint_excludes_not_included_rows(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    # detection_logic="updated_2026" keeps this scoped away from the demo
    # seed's baseline include=True rows (see the empty-data test above) - the
    # only "updated_2026" row anywhere is this include=False one.
    _seed_processed_reading(app, include=False, detection_logic="updated_2026")

    response = client.post(
        "/api/trends/rain-rate-vs-level", json={"detection_logic": "updated_2026"}
    )

    chart = response.get_json()["rain_rate_vs_level_chart"]
    assert chart["data"] == []


def test_rain_rate_vs_level_endpoint_excludes_dry_readings_by_default(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    # detection_logic="updated_2026" keeps this scoped away from the demo
    # seed's baseline rows, same trick as the other isolated tests above.
    _seed_processed_reading(app, detection_logic="updated_2026", is_wet=False, rain1=0.0)
    _seed_processed_reading(
        app,
        detection_logic="updated_2026",
        is_wet=True,
        rain1=3.0,
        datetime=datetime(2026, 8, 3, 23, 15, 0),
    )

    default_response = client.post(
        "/api/trends/rain-rate-vs-level", json={"detection_logic": "updated_2026"}
    )
    default_chart = default_response.get_json()["rain_rate_vs_level_chart"]
    assert default_chart["data"][0]["x"] == [3.0]  # only the wet reading

    include_dry_response = client.post(
        "/api/trends/rain-rate-vs-level",
        json={"detection_logic": "updated_2026", "include_dry": True},
    )
    include_dry_chart = include_dry_response.get_json()["rain_rate_vs_level_chart"]
    assert include_dry_chart["data"][0]["x"] == [0.0, 3.0]  # both


def _seed_rain_rate_fit(app, **overrides):
    defaults = dict(
        noise_site_id=KNOWN_SITE,
        detection_logic="updated_2026",
        metric="l90",
        slope=4.0,
        intercept=40.0,
        r_squared=0.8,
        sample_count=10,
        computed_at=datetime(2026, 8, 3, 0, 0, 0),
    )
    defaults.update(overrides)
    with app.app_context():
        db.session.add(RainRateFit(**defaults))
        db.session.commit()


def test_rain_rate_vs_level_endpoint_includes_a_fit_line_when_one_is_stored(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    # detection_logic="updated_2026" keeps this scoped away from the demo
    # seed's baseline rows, same trick as the other isolated tests above.
    _seed_processed_reading(
        app, detection_logic="updated_2026", rain1=1.0, l90=40.0,
        datetime=datetime(2026, 8, 3, 23, 0, 0),
    )
    _seed_processed_reading(
        app, detection_logic="updated_2026", rain1=2.0, l90=44.0,
        datetime=datetime(2026, 8, 3, 23, 15, 0),
    )
    _seed_rain_rate_fit(app)

    response = client.post(
        "/api/trends/rain-rate-vs-level",
        json={"detection_logic": "updated_2026", "metric": "l90"},
    )

    assert response.status_code == 200
    chart = response.get_json()["rain_rate_vs_level_chart"]
    assert len(chart["data"]) == 2
    assert chart["data"][1]["mode"] == "lines"


def test_rain_rate_vs_level_endpoint_rejects_invalid_detection_logic(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.post("/api/trends/rain-rate-vs-level", json={"detection_logic": "bogus"})

    assert response.status_code == 400


def test_rain_rate_vs_level_endpoint_rejects_invalid_metric(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.post("/api/trends/rain-rate-vs-level", json={"metric": "leq"})

    assert response.status_code == 400
