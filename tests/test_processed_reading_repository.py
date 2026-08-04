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


OTHER_SITE = 51  # from data/site.csv, seeded with demo ProcessedReading rows


def test_list_readings_per_site_limit_keeps_most_recent_rows_per_site(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        # KNOWN_SITE gets more rows than the cap, OTHER_SITE gets fewer -
        # a flat LIMIT after ORDER BY noise_site_id would silently drop
        # whichever site sorts later; per_site_limit must not do that.
        # Scoped to detection_logic="updated_2026" (zero seeded baseline
        # rows there, per CLAUDE.md) so exact counts below aren't polluted
        # by the 50 "original" demo rows already seeded for these sites.
        heavy_dates = [datetime(2025, 1, day) for day in range(1, 11)]  # 10 rows
        light_dates = [datetime(2025, 1, day) for day in range(1, 4)]  # 3 rows
        for dt in heavy_dates:
            reading = _reading(dt, include=True)
            reading.detection_logic = "updated_2026"
            db.session.add(reading)
        for dt in light_dates:
            reading = _reading(dt, include=True)
            reading.noise_site_id = OTHER_SITE
            reading.detection_logic = "updated_2026"
            db.session.add(reading)
        db.session.commit()

        repository = ProcessedReadingRepository()
        results = repository.list_readings(
            site_ids=[KNOWN_SITE, OTHER_SITE],
            detection_logic="updated_2026",
            per_site_limit=5,
        )

        by_site = {}
        for reading in results:
            by_site.setdefault(reading.noise_site_id, []).append(reading.datetime)

        assert len(by_site[KNOWN_SITE]) == 5
        assert sorted(by_site[KNOWN_SITE]) == heavy_dates[-5:]  # most recent 5, not the earliest
        assert len(by_site[OTHER_SITE]) == 3  # under the cap, untouched
        assert sorted(by_site[OTHER_SITE]) == light_dates

        uncapped = repository.list_readings(
            site_ids=[KNOWN_SITE, OTHER_SITE],
            detection_logic="updated_2026",
            per_site_limit=None,
        )
        assert len(uncapped) == 13
