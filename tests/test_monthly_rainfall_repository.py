from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_rainfall import (
    MonthlyRainfall,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_rainfall_repository import (
    MonthlyRainfallRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _month(noise_site_id, month, avg_rain_mm=2.0, sample_count=10):
    return MonthlyRainfall(
        noise_site_id=noise_site_id,
        month=month,
        avg_rain_mm=avg_rain_mm,
        sample_count=sample_count,
        computed_at=datetime(2026, 8, 4, 0, 0, 0),
    )


def test_list_months_filters_by_noise_site_id(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_month(SITE_A, 1))
        db.session.add(_month(SITE_B, 6))
        db.session.commit()

        repository = MonthlyRainfallRepository()

        scoped = repository.list_months(noise_site_id=[SITE_A])
        assert [m.noise_site_id for m in scoped] == [SITE_A]

        unfiltered = repository.list_months()
        assert {m.noise_site_id for m in unfiltered} == {SITE_A, SITE_B}


def test_replace_all_fully_replaces_prior_contents(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_month(SITE_A, 1))
        db.session.commit()

        repository = MonthlyRainfallRepository()
        written = repository.replace_all(
            [
                {
                    "noise_site_id": SITE_B,
                    "month": 6,
                    "avg_rain_mm": 4.5,
                    "sample_count": 7,
                    "computed_at": datetime(2026, 8, 4, 0, 0, 0),
                }
            ]
        )

        assert written == 1
        remaining = repository.list_months()
        assert [(m.noise_site_id, m.month) for m in remaining] == [(SITE_B, 6)]
