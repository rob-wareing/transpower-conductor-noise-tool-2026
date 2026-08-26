from datetime import date, datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import site_climate_service
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_rainfall import (
    MonthlyRainfall,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.outage import Outage
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading_availability import (
    ReadingAvailability,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.wind_rose import WindRose

SITE = 142  # from data/site.csv - no baseline seeded reconductoring or outage rows


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def test_get_wind_rose_collapses_multiple_months_weighted_by_sample_count(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            WindRose(
                noise_site_id=SITE,
                year=2025,
                month=1,
                direction_sector="N",
                sample_count=10,
                avg_wind_speed=2.0,
                computed_at=datetime(2026, 8, 4),
            )
        )
        db.session.add(
            WindRose(
                noise_site_id=SITE,
                year=2025,
                month=2,
                direction_sector="N",
                sample_count=30,
                avg_wind_speed=6.0,
                computed_at=datetime(2026, 8, 4),
            )
        )
        db.session.commit()

        rows = {row.direction_sector: row for row in site_climate_service.get_wind_rose(SITE)}

        assert rows["N"].sample_count == 40
        # weighted mean: (10*2 + 30*6) / 40 = 5.0
        assert rows["N"].avg_wind_speed == 5.0


def test_get_wind_rose_scopes_to_requested_range(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            WindRose(
                noise_site_id=SITE,
                year=2024,
                month=1,
                direction_sector="N",
                sample_count=10,
                avg_wind_speed=2.0,
                computed_at=datetime(2026, 8, 4),
            )
        )
        db.session.add(
            WindRose(
                noise_site_id=SITE,
                year=2026,
                month=1,
                direction_sector="N",
                sample_count=10,
                avg_wind_speed=8.0,
                computed_at=datetime(2026, 8, 4),
            )
        )
        db.session.commit()

        rows = {
            row.direction_sector: row
            for row in site_climate_service.get_wind_rose(SITE, start=(2025, 1), end=(2026, 12))
        }

        assert rows["N"].sample_count == 10
        assert rows["N"].avg_wind_speed == 8.0


def test_get_monthly_rainfall_collapses_multiple_years_into_calendar_month(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(
            MonthlyRainfall(
                noise_site_id=SITE,
                year=2024,
                month=1,
                avg_rain_mm=10.0,
                total_rain=10.0,
                sample_count=1,
                computed_at=datetime(2026, 8, 4),
            )
        )
        db.session.add(
            MonthlyRainfall(
                noise_site_id=SITE,
                year=2025,
                month=1,
                avg_rain_mm=20.0,
                total_rain=20.0,
                sample_count=1,
                computed_at=datetime(2026, 8, 4),
            )
        )
        db.session.commit()

        rows = {row.month: row for row in site_climate_service.get_monthly_rainfall(SITE)}

        assert rows[1].sample_count == 2
        assert rows[1].total_rain == 30.0
        assert rows[1].avg_rain_mm == 15.0


def test_get_site_summary_bundles_reconductoring_outages_availability_and_event_counts(
    tmp_path, monkeypatch
):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
            ProcessedReadingRepository,
        )

        before_counts = ProcessedReadingRepository().count_by_detection_logic(SITE, include=True)

        db.session.add(
            Reconductoring(noise_site_id=SITE, reconductoring_date=date(2024, 3, 1))
        )
        db.session.add(
            Outage(
                noise_site_id=SITE,
                outage_type="monitoring",
                start_datetime=datetime(2024, 1, 1),
                end_datetime=datetime(2024, 1, 2),
            )
        )
        db.session.add(
            ReadingAvailability(
                noise_site_id=SITE,
                min_datetime=datetime(2019, 1, 1),
                max_datetime=datetime(2026, 1, 1),
                row_count=1000,
                computed_at=datetime(2026, 8, 22),
            )
        )
        db.session.commit()

        summary = site_climate_service.get_site_summary(SITE)

        assert len(summary.reconductoring_events) == 1
        assert summary.reconductoring_events[0].reconductoring_date == date(2024, 3, 1)
        assert len(summary.outages) == 1
        assert summary.outages[0].outage_type == "monitoring"
        assert summary.availability_start == datetime(2019, 1, 1)
        assert summary.availability_end == datetime(2026, 1, 1)
        # No new processed_reading rows added by this test, so counts should
        # be unchanged from whatever the baseline seed already contributed.
        assert summary.detected_event_count_original == before_counts["original"]
        assert summary.detected_event_count_updated_2026 == before_counts["updated_2026"]


def test_get_site_summary_handles_site_with_no_history(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        summary = site_climate_service.get_site_summary(SITE)

        assert summary.reconductoring_events == []
        assert summary.outages == []
        assert summary.availability_start is None
        assert summary.availability_end is None
