from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.outage import Outage
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.outage_repository import (
    OutageRepository,
)

SITE_A = 142  # from data/site.csv - no baseline seeded outage row (unlike 51/115/137)
SITE_B = 144  # from data/site.csv - no baseline seeded outage row (unlike 51/115/137)


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _outage(noise_site_id, start=datetime(2024, 1, 1), end=datetime(2024, 1, 2)):
    return Outage(
        noise_site_id=noise_site_id,
        outage_type="monitoring",
        start_datetime=start,
        end_datetime=end,
    )


def test_list_outages_filters_by_noise_site_id(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_outage(SITE_A))
        db.session.add(_outage(SITE_B))
        db.session.commit()

        scoped = OutageRepository().list_outages(noise_site_id=SITE_A)

        assert [outage.noise_site_id for outage in scoped] == [SITE_A]

        unfiltered = OutageRepository().list_outages()
        assert {SITE_A, SITE_B} <= {outage.noise_site_id for outage in unfiltered}
