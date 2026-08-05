from datetime import date

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)

SITE_A = 137  # from data/site.csv - no baseline seeded reconductoring row (unlike 51/115)
SITE_B = 142  # from data/site.csv - no baseline seeded reconductoring row (unlike 51/115)


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _event(noise_site_id, reconductoring_date):
    return Reconductoring(noise_site_id=noise_site_id, reconductoring_date=reconductoring_date)


def test_latest_by_site_returns_the_most_recent_date_per_site(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_event(SITE_A, date(2022, 1, 1)))
        db.session.add(_event(SITE_A, date(2024, 6, 1)))  # the most recent for SITE_A
        db.session.add(_event(SITE_B, date(2023, 3, 15)))
        db.session.commit()

        cutoffs = ReconductoringRepository().latest_by_site()

        # latest_by_site() is global (not scoped to specific sites), so it
        # also returns the demo seed's own baseline sites (51/115) - assert
        # on just the entries this test cares about, not the whole dict.
        assert cutoffs[SITE_A] == date(2024, 6, 1)
        assert cutoffs[SITE_B] == date(2023, 3, 15)


def test_latest_by_site_has_no_entry_for_sites_with_no_events(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_event(SITE_A, date(2022, 1, 1)))
        db.session.commit()

        cutoffs = ReconductoringRepository().latest_by_site()

        assert SITE_B not in cutoffs
