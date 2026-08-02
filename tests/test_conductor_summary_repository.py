from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.conductor_summary import (
    ConductorSummary,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_summary_repository import (
    ConductorSummaryRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _summary(noise_site_id):
    return ConductorSummary(
        noise_site_id=noise_site_id,
        detection_logic="original",
        measurement_duration_minutes=15,
        l90_mean=40.0, l90_max=48.0, l90_min=35.0, l90_median=41.0, l90_q1=38.0, l90_q3=44.0,
        tone_100hz_mean=1.0, tone_100hz_max=2.0, tone_100hz_min=0.5,
        tone_100hz_median=1.2, tone_100hz_q1=0.8, tone_100hz_q3=1.5,
        tone_200hz_mean=0.9, tone_200hz_max=1.8, tone_200hz_min=0.4,
        tone_200hz_median=1.0, tone_200hz_q1=0.7, tone_200hz_q3=1.3,
        sample_count=10,
        computed_at=datetime(2026, 8, 3, 0, 0, 0),
    )


def test_list_summaries_filters_by_noise_site_id(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_summary(SITE_A))
        db.session.add(_summary(SITE_B))
        db.session.commit()

        repository = ConductorSummaryRepository()

        scoped = repository.list_summaries(noise_site_id=[SITE_A])
        assert [s.noise_site_id for s in scoped] == [SITE_A]

        unfiltered = repository.list_summaries()
        assert {s.noise_site_id for s in unfiltered} == {SITE_A, SITE_B}
