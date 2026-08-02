from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)

KNOWN_SITE = 115  # from data/site.csv, seeded with demo ProcessedReading rows


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _reading(dt, include):
    return ProcessedReading(
        noise_site_id=KNOWN_SITE,
        datetime=dt,
        l90=45.0,
        tone_100hz=1.0,
        tone_200hz=1.0,
        rain1=0.0,
        rain2=0.0,
        is_wet=True,
        include=include,
        measurement_duration_minutes=15,
        detection_logic="original",
    )


def test_list_readings_filters_by_include(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        included_dt = datetime(2025, 6, 1, 23, 0)
        excluded_dt = datetime(2025, 6, 1, 23, 15)
        db.session.add(_reading(included_dt, include=True))
        db.session.add(_reading(excluded_dt, include=False))
        db.session.commit()

        repository = ProcessedReadingRepository()

        included = repository.list_readings(site_ids=[KNOWN_SITE], include=True)
        assert all(reading.include for reading in included)
        assert any(reading.datetime == included_dt for reading in included)
        assert not any(reading.datetime == excluded_dt for reading in included)

        excluded = repository.list_readings(site_ids=[KNOWN_SITE], include=False)
        assert all(not reading.include for reading in excluded)
        assert any(reading.datetime == excluded_dt for reading in excluded)
        assert not any(reading.datetime == included_dt for reading in excluded)

        unfiltered = repository.list_readings(site_ids=[KNOWN_SITE])
        assert any(reading.datetime == included_dt for reading in unfiltered)
        assert any(reading.datetime == excluded_dt for reading in unfiltered)
