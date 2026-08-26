from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_weather_stats import (
    MonthlyWeatherStats,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_weather_stats_repository import (
    MonthlyWeatherStatsRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _month(noise_site_id, year, month, sample_count=10):
    return MonthlyWeatherStats(
        noise_site_id=noise_site_id,
        year=year,
        month=month,
        min_rain_mm=0.5,
        max_rain_mm=5.0,
        avg_rain_mm=2.0,
        min_wind_speed=1.0,
        max_wind_speed=10.0,
        avg_wind_speed=5.0,
        sample_count=sample_count,
        computed_at=datetime(2026, 8, 4, 0, 0, 0),
    )


def test_list_months_filters_by_noise_site_id(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_month(SITE_A, 2026, 1))
        db.session.add(_month(SITE_B, 2026, 1))
        db.session.commit()

        repository = MonthlyWeatherStatsRepository()

        scoped = repository.list_months(noise_site_id=[SITE_A])
        assert [m.noise_site_id for m in scoped] == [SITE_A]

        unfiltered = repository.list_months()
        assert {m.noise_site_id for m in unfiltered} == {SITE_A, SITE_B}


def test_list_months_filters_by_year_month_range(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_month(SITE_A, 2024, 12))
        db.session.add(_month(SITE_A, 2025, 6))
        db.session.add(_month(SITE_A, 2026, 1))
        db.session.commit()

        repository = MonthlyWeatherStatsRepository()

        scoped = repository.list_months(
            noise_site_id=[SITE_A], start_year_month=202501, end_year_month=202512
        )
        assert [(m.year, m.month) for m in scoped] == [(2025, 6)]


def test_replace_all_fully_replaces_prior_contents(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_month(SITE_A, 2026, 1))
        db.session.commit()

        repository = MonthlyWeatherStatsRepository()
        written = repository.replace_all(
            [
                {
                    "noise_site_id": SITE_B,
                    "year": 2026,
                    "month": 6,
                    "min_rain_mm": 0.0,
                    "max_rain_mm": 1.0,
                    "avg_rain_mm": 0.5,
                    "min_wind_speed": 2.0,
                    "max_wind_speed": 4.0,
                    "avg_wind_speed": 3.0,
                    "sample_count": 5,
                    "computed_at": datetime(2026, 8, 4, 0, 0, 0),
                }
            ]
        )

        assert written == 1
        remaining = repository.list_months()
        assert [(m.noise_site_id, m.year, m.month) for m in remaining] == [(SITE_B, 2026, 6)]


def test_replace_all_with_empty_records_clears_table(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_month(SITE_A, 2026, 1))
        db.session.commit()

        written = MonthlyWeatherStatsRepository().replace_all([])

        assert written == 0
        assert MonthlyWeatherStatsRepository().list_months() == []
