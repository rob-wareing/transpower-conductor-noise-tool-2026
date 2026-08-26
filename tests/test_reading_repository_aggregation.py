from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading import Reading
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_repository import (
    ReadingRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _reading(noise_site_id, dt, wind_direction=None, wind_speed=None, rain_mm=None):
    return Reading(
        noise_site_id=noise_site_id,
        datetime=dt,
        leq=50.0,
        l90=45.0,
        leq_80hz=1.0,
        leq_100hz=1.0,
        leq_125hz=1.0,
        leq_160hz=1.0,
        leq_200hz=1.0,
        leq_250hz=1.0,
        wind_direction=wind_direction,
        wind_speed=wind_speed,
        rain_mm=rain_mm,
    )


def test_aggregate_wind_rose_buckets_sector_boundaries_correctly(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        # N spans [348.75, 360) U [0, 11.25); NNE starts at 11.25.
        db.session.add(_reading(SITE_A, datetime(2025, 1, 1), 348.75, 5.0))
        db.session.add(_reading(SITE_A, datetime(2025, 1, 2), 11.24, 6.0))
        db.session.add(_reading(SITE_A, datetime(2025, 1, 3), 11.26, 7.0))
        db.session.add(_reading(SITE_A, datetime(2025, 1, 4), 0, 3.0))
        db.session.add(_reading(SITE_A, datetime(2025, 1, 5), 360, 4.0))
        db.session.commit()

        rows = {row["direction_sector"]: row for row in ReadingRepository().aggregate_wind_rose()}

        assert rows["N"]["sample_count"] == 4
        assert rows["N"]["avg_wind_speed"] == (5.0 + 6.0 + 3.0 + 4.0) / 4
        assert rows["NNE"]["sample_count"] == 1
        assert rows["NNE"]["avg_wind_speed"] == 7.0


def test_aggregate_wind_rose_excludes_sentinel_and_null_values(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 1, 1), 90, 999.9))  # ingestion sentinel
        db.session.add(_reading(SITE_A, datetime(2025, 1, 2), 90, 244.7))  # implausible glitch
        db.session.add(_reading(SITE_A, datetime(2025, 1, 3), 90, None))  # missing speed
        db.session.add(_reading(SITE_A, datetime(2025, 1, 4), None, 5.0))  # missing direction
        db.session.add(_reading(SITE_A, datetime(2025, 1, 5), 90, 5.0))  # the one valid row
        db.session.commit()

        rows = ReadingRepository().aggregate_wind_rose()

        assert len(rows) == 1
        assert rows[0]["direction_sector"] == "E"
        assert rows[0]["sample_count"] == 1
        assert rows[0]["avg_wind_speed"] == 5.0


def test_aggregate_wind_rose_is_scoped_per_site(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 1, 1), 0, 5.0))
        db.session.add(_reading(SITE_B, datetime(2025, 1, 1), 180, 10.0))
        db.session.commit()

        rows = ReadingRepository().aggregate_wind_rose(noise_site_id=[SITE_A])

        assert len(rows) == 1
        assert rows[0]["noise_site_id"] == SITE_A


def test_aggregate_monthly_rainfall_groups_by_year_and_month_separately(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2020, 1, 10), rain_mm=10.0))
        db.session.add(_reading(SITE_A, datetime(2021, 1, 10), rain_mm=20.0))
        db.session.add(_reading(SITE_A, datetime(2020, 2, 1), rain_mm=5.0))
        db.session.commit()

        rows = {
            (row["year"], row["month"]): row for row in ReadingRepository().aggregate_monthly_rainfall()
        }

        assert rows[(2020, 1)]["sample_count"] == 1
        assert rows[(2020, 1)]["avg_rain_mm"] == 10.0
        assert rows[(2020, 1)]["total_rain"] == 10.0
        assert rows[(2021, 1)]["sample_count"] == 1
        assert rows[(2021, 1)]["avg_rain_mm"] == 20.0
        assert rows[(2021, 1)]["total_rain"] == 20.0
        assert rows[(2020, 2)]["sample_count"] == 1
        assert rows[(2020, 2)]["avg_rain_mm"] == 5.0
        assert rows[(2020, 2)]["total_rain"] == 5.0


def test_aggregate_monthly_rainfall_excludes_sentinel_and_null_values(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 3, 1), rain_mm=99.9))  # ingestion sentinel
        db.session.add(_reading(SITE_A, datetime(2025, 3, 2), rain_mm=None))  # missing
        db.session.add(_reading(SITE_A, datetime(2025, 3, 3), rain_mm=2.0))  # valid
        db.session.commit()

        rows = ReadingRepository().aggregate_monthly_rainfall()

        assert len(rows) == 1
        assert rows[0]["year"] == 2025
        assert rows[0]["month"] == 3
        assert rows[0]["sample_count"] == 1
        assert rows[0]["avg_rain_mm"] == 2.0
        assert rows[0]["total_rain"] == 2.0


def test_aggregate_wind_rose_includes_year_and_groups_separately_per_month(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2020, 1, 1), 0, 5.0))
        db.session.add(_reading(SITE_A, datetime(2021, 1, 1), 0, 15.0))
        db.session.commit()

        rows = {
            (row["year"], row["month"]): row for row in ReadingRepository().aggregate_wind_rose()
        }

        assert rows[(2020, 1)]["sample_count"] == 1
        assert rows[(2020, 1)]["avg_wind_speed"] == 5.0
        assert rows[(2021, 1)]["sample_count"] == 1
        assert rows[(2021, 1)]["avg_wind_speed"] == 15.0


def test_aggregate_monthly_weather_stats_computes_min_max_avg_per_metric(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 6, 1), wind_speed=2.0, rain_mm=1.0))
        db.session.add(_reading(SITE_A, datetime(2025, 6, 2), wind_speed=8.0, rain_mm=4.0))
        db.session.add(_reading(SITE_A, datetime(2025, 6, 3), wind_speed=5.0, rain_mm=None))
        db.session.commit()

        rows = ReadingRepository().aggregate_monthly_weather_stats()

        assert len(rows) == 1
        row = rows[0]
        assert row["year"] == 2025
        assert row["month"] == 6
        assert row["sample_count"] == 3  # every reading row, regardless of null fields
        assert row["min_rain_mm"] == 1.0
        assert row["max_rain_mm"] == 4.0
        assert row["avg_rain_mm"] == 2.5  # averaged only over the 2 non-null rain rows
        assert row["min_wind_speed"] == 2.0
        assert row["max_wind_speed"] == 8.0
        assert row["avg_wind_speed"] == 5.0


def test_aggregate_monthly_weather_stats_excludes_sentinel_values_per_metric(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 7, 1), wind_speed=999.9, rain_mm=99.9))
        db.session.add(_reading(SITE_A, datetime(2025, 7, 2), wind_speed=6.0, rain_mm=3.0))
        db.session.commit()

        rows = ReadingRepository().aggregate_monthly_weather_stats()

        assert len(rows) == 1
        row = rows[0]
        assert row["sample_count"] == 2
        assert row["avg_rain_mm"] == 3.0
        assert row["avg_wind_speed"] == 6.0


def test_aggregate_monthly_weather_stats_is_scoped_per_site(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 1, 1), wind_speed=1.0, rain_mm=1.0))
        db.session.add(_reading(SITE_B, datetime(2025, 1, 1), wind_speed=2.0, rain_mm=2.0))
        db.session.commit()

        rows = ReadingRepository().aggregate_monthly_weather_stats(noise_site_id=[SITE_A])

        assert len(rows) == 1
        assert rows[0]["noise_site_id"] == SITE_A
