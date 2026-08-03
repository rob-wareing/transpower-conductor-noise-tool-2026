from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.rain_rate_fit import (
    RainRateFit,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.rain_rate_fit_repository import (
    RainRateFitRepository,
)

SITE_A = 115  # from data/site.csv
SITE_B = 137  # from data/site.csv


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def _fit(noise_site_id, metric="l90"):
    return RainRateFit(
        noise_site_id=noise_site_id,
        detection_logic="original",
        metric=metric,
        slope=4.0,
        intercept=40.0,
        r_squared=0.8,
        sample_count=10,
        computed_at=datetime(2026, 8, 3, 0, 0, 0),
    )


def test_list_fits_filters_by_noise_site_id(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_fit(SITE_A))
        db.session.add(_fit(SITE_B))
        db.session.commit()

        repository = RainRateFitRepository()

        scoped = repository.list_fits(noise_site_id=[SITE_A])
        assert [f.noise_site_id for f in scoped] == [SITE_A]

        unfiltered = repository.list_fits()
        assert {f.noise_site_id for f in unfiltered} == {SITE_A, SITE_B}


def test_list_fits_filters_by_metric(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_fit(SITE_A, metric="l90"))
        db.session.add(_fit(SITE_A, metric="tone_100hz"))
        db.session.commit()

        repository = RainRateFitRepository()

        scoped = repository.list_fits(metric="tone_100hz")
        assert [f.metric for f in scoped] == ["tone_100hz"]


def test_replace_all_deletes_existing_rows_and_inserts_the_new_set(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(_fit(SITE_A))
        db.session.commit()

        repository = RainRateFitRepository()
        written = repository.replace_all(
            [
                {
                    "noise_site_id": SITE_B,
                    "detection_logic": "original",
                    "metric": "l90",
                    "slope": 5.0,
                    "intercept": 41.0,
                    "r_squared": 0.9,
                    "sample_count": 12,
                    "computed_at": datetime(2026, 8, 3, 0, 0, 0),
                }
            ]
        )

        assert written == 1
        remaining = repository.list_fits()
        assert [f.noise_site_id for f in remaining] == [SITE_B]
