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


def test_aggregate_monthly_rainfall_groups_climatologically_across_years(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2020, 1, 10), rain_mm=10.0))
        db.session.add(_reading(SITE_A, datetime(2021, 1, 10), rain_mm=20.0))
        db.session.add(_reading(SITE_A, datetime(2020, 2, 1), rain_mm=5.0))
        db.session.commit()

        rows = {row["month"]: row for row in ReadingRepository().aggregate_monthly_rainfall()}

        assert rows[1]["sample_count"] == 2
        assert rows[1]["avg_rain_mm"] == 15.0
        assert rows[2]["sample_count"] == 1
        assert rows[2]["avg_rain_mm"] == 5.0


def test_aggregate_monthly_rainfall_excludes_sentinel_and_null_values(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_reading(SITE_A, datetime(2025, 3, 1), rain_mm=99.9))  # ingestion sentinel
        db.session.add(_reading(SITE_A, datetime(2025, 3, 2), rain_mm=None))  # missing
        db.session.add(_reading(SITE_A, datetime(2025, 3, 3), rain_mm=2.0))  # valid
        db.session.commit()

        rows = ReadingRepository().aggregate_monthly_rainfall()

        assert len(rows) == 1
        assert rows[0]["month"] == 3
        assert rows[0]["sample_count"] == 1
        assert rows[0]["avg_rain_mm"] == 2.0
