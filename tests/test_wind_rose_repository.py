from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.wind_rose import WindRose
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.wind_rose_repository import (
    WindRoseRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _sector(noise_site_id, direction_sector, sample_count=10, avg_wind_speed=5.0):
    return WindRose(
        noise_site_id=noise_site_id,
        direction_sector=direction_sector,
        sample_count=sample_count,
        avg_wind_speed=avg_wind_speed,
        computed_at=datetime(2026, 8, 4, 0, 0, 0),
    )


def test_list_sectors_filters_by_noise_site_id(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_sector(SITE_A, "N"))
        db.session.add(_sector(SITE_B, "S"))
        db.session.commit()

        repository = WindRoseRepository()

        scoped = repository.list_sectors(noise_site_id=[SITE_A])
        assert [s.noise_site_id for s in scoped] == [SITE_A]

        unfiltered = repository.list_sectors()
        assert {s.noise_site_id for s in unfiltered} == {SITE_A, SITE_B}


def test_replace_all_fully_replaces_prior_contents(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_sector(SITE_A, "N"))
        db.session.commit()

        repository = WindRoseRepository()
        written = repository.replace_all(
            [
                {
                    "noise_site_id": SITE_B,
                    "direction_sector": "S",
                    "sample_count": 3,
                    "avg_wind_speed": 2.0,
                    "computed_at": datetime(2026, 8, 4, 0, 0, 0),
                }
            ]
        )

        assert written == 1
        remaining = repository.list_sectors()
        assert [(s.noise_site_id, s.direction_sector) for s in remaining] == [(SITE_B, "S")]


def test_replace_all_with_empty_records_clears_table(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_sector(SITE_A, "N"))
        db.session.commit()

        written = WindRoseRepository().replace_all([])

        assert written == 0
        assert WindRoseRepository().list_sectors() == []
