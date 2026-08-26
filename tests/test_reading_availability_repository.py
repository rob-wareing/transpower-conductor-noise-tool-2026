from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading_availability import (
    ReadingAvailability,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_availability_repository import (
    ReadingAvailabilityRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _availability(noise_site_id, min_datetime=datetime(2018, 1, 1), max_datetime=datetime(2025, 1, 1)):
    return ReadingAvailability(
        noise_site_id=noise_site_id,
        min_datetime=min_datetime,
        max_datetime=max_datetime,
        row_count=100,
        computed_at=datetime(2026, 8, 22, 0, 0, 0),
    )


def test_list_all_returns_every_site_ordered(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_availability(SITE_B))
        db.session.add(_availability(SITE_A))
        db.session.commit()

        rows = ReadingAvailabilityRepository().list_all()

        assert [row.noise_site_id for row in rows] == [SITE_A, SITE_B]


def test_find_by_site_returns_matching_row(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_availability(SITE_A, min_datetime=datetime(2019, 1, 1)))
        db.session.add(_availability(SITE_B))
        db.session.commit()

        found = ReadingAvailabilityRepository().find_by_site(SITE_A)

        assert found is not None
        assert found.noise_site_id == SITE_A
        assert found.min_datetime == datetime(2019, 1, 1)


def test_find_by_site_returns_none_for_unknown_site(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        assert ReadingAvailabilityRepository().find_by_site(SITE_A) is None


def test_replace_all_fully_replaces_prior_contents(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_availability(SITE_A))
        db.session.commit()

        repository = ReadingAvailabilityRepository()
        written = repository.replace_all(
            [
                {
                    "noise_site_id": SITE_B,
                    "min_datetime": datetime(2020, 1, 1),
                    "max_datetime": datetime(2026, 1, 1),
                    "row_count": 50,
                    "computed_at": datetime(2026, 8, 22, 0, 0, 0),
                }
            ]
        )

        assert written == 1
        remaining = repository.list_all()
        assert [row.noise_site_id for row in remaining] == [SITE_B]


def test_replace_all_with_empty_records_clears_table(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_availability(SITE_A))
        db.session.commit()

        written = ReadingAvailabilityRepository().replace_all([])

        assert written == 0
        assert ReadingAvailabilityRepository().list_all() == []
