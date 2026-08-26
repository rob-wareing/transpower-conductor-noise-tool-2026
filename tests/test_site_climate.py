from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_rainfall import (
    MonthlyRainfall,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_weather_stats import (
    MonthlyWeatherStats,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.wind_rose import WindRose

KNOWN_SITE = 115  # from data/site.csv


def _make_app_and_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app, app.test_client()


def test_wind_rose_endpoint_returns_populated_site_data(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            WindRose(
                noise_site_id=KNOWN_SITE,
                year=2026,
                month=1,
                direction_sector="N",
                sample_count=42,
                avg_wind_speed=5.5,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/wind-rose")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["items"][0] == {
        "direction_sector": "N",
        "sample_count": 42,
        "avg_wind_speed": 5.5,
    }


def test_wind_rose_endpoint_returns_empty_items_for_site_with_no_data(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.get(f"/api/sites/{KNOWN_SITE}/wind-rose")

    assert response.status_code == 200
    assert response.get_json() == {"items": [], "count": 0}


def test_wind_rose_endpoint_scopes_by_start_end_range(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            WindRose(
                noise_site_id=KNOWN_SITE,
                year=2024,
                month=6,
                direction_sector="N",
                sample_count=10,
                avg_wind_speed=2.0,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.add(
            WindRose(
                noise_site_id=KNOWN_SITE,
                year=2026,
                month=1,
                direction_sector="N",
                sample_count=20,
                avg_wind_speed=8.0,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/wind-rose?start=2025-01&end=2026-12")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["items"][0]["sample_count"] == 20
    assert payload["items"][0]["avg_wind_speed"] == 8.0


def test_monthly_rainfall_endpoint_returns_populated_site_data(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            MonthlyRainfall(
                noise_site_id=KNOWN_SITE,
                year=2026,
                month=6,
                avg_rain_mm=3.25,
                total_rain=55.25,
                sample_count=17,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/monthly-rainfall")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["items"][0] == {
        "month": 6,
        "avg_rain_mm": 3.25,
        "total_rain": 55.25,
        "sample_count": 17,
    }


def test_monthly_rainfall_endpoint_returns_empty_items_for_site_with_no_data(tmp_path, monkeypatch):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.get(f"/api/sites/{KNOWN_SITE}/monthly-rainfall")

    assert response.status_code == 200
    assert response.get_json() == {"items": [], "count": 0}


def test_monthly_rainfall_endpoint_scopes_by_start_end_range(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            MonthlyRainfall(
                noise_site_id=KNOWN_SITE,
                year=2024,
                month=6,
                avg_rain_mm=1.0,
                total_rain=10.0,
                sample_count=5,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.add(
            MonthlyRainfall(
                noise_site_id=KNOWN_SITE,
                year=2026,
                month=1,
                avg_rain_mm=2.0,
                total_rain=20.0,
                sample_count=10,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/monthly-rainfall?start=2025-01")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["items"][0]["total_rain"] == 20.0


def test_wind_rose_endpoint_scopes_to_requested_site_only(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    other_site = 137  # from data/site.csv
    with app.app_context():
        db.session.add(
            WindRose(
                noise_site_id=other_site,
                year=2026,
                month=1,
                direction_sector="S",
                sample_count=1,
                avg_wind_speed=1.0,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/wind-rose")

    assert response.status_code == 200
    assert response.get_json() == {"items": [], "count": 0}


def test_monthly_weather_stats_endpoint_returns_populated_site_data(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            MonthlyWeatherStats(
                noise_site_id=KNOWN_SITE,
                year=2026,
                month=6,
                min_rain_mm=0.5,
                max_rain_mm=5.0,
                avg_rain_mm=2.0,
                min_wind_speed=1.0,
                max_wind_speed=10.0,
                avg_wind_speed=5.0,
                sample_count=17,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/monthly-weather-stats")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["items"][0] == {
        "year": 2026,
        "month": 6,
        "min_rain_mm": 0.5,
        "max_rain_mm": 5.0,
        "avg_rain_mm": 2.0,
        "min_wind_speed": 1.0,
        "max_wind_speed": 10.0,
        "avg_wind_speed": 5.0,
        "sample_count": 17,
    }


def test_monthly_weather_stats_endpoint_scopes_by_start_end_range(tmp_path, monkeypatch):
    app, client = _make_app_and_client(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            MonthlyWeatherStats(
                noise_site_id=KNOWN_SITE,
                year=2024,
                month=6,
                sample_count=5,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.add(
            MonthlyWeatherStats(
                noise_site_id=KNOWN_SITE,
                year=2026,
                month=1,
                sample_count=9,
                computed_at=datetime(2026, 8, 4, 0, 0, 0),
            )
        )
        db.session.commit()

    response = client.get(f"/api/sites/{KNOWN_SITE}/monthly-weather-stats?start=2025-01&end=2026-12")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["items"][0]["sample_count"] == 9


def test_monthly_weather_stats_endpoint_returns_empty_items_for_site_with_no_data(
    tmp_path, monkeypatch
):
    _app, client = _make_app_and_client(tmp_path, monkeypatch)

    response = client.get(f"/api/sites/{KNOWN_SITE}/monthly-weather-stats")

    assert response.status_code == 200
    assert response.get_json() == {"items": [], "count": 0}
