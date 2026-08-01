import pandas as pd
import pytest

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import processing_service
from transpower_conductor_noise_tool_2026.backend.ingestion import ingestion_job
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading import Reading

KNOWN_SITE = 115  # from data/site.csv, not in IGNORE_SITES
OTHER_KNOWN_SITE = 137  # from data/site.csv, not in IGNORE_SITES
IGNORED_SITE = 51  # in data/site.csv, but also in IGNORE_SITES
UNKNOWN_SITE = 9999  # not in data/site.csv at all

# A real 10-value slice from local_data/example_leq900.txt (all valid, no "A"
# tokens) - enough to exercise a real calculate_leq_rmse computation here
# rather than a synthetic string.
LEQ900_SAMPLE = "44.5|45.4|44.6|44.2|42.8|42.8|44.0|44.6|44.5|44.2"


class FakeClient:
    def __init__(self, sites, events_by_site):
        self._sites = sites
        self._events_by_site = events_by_site

    def sites(self):
        return self._sites

    def collect_events(self, site_id, noise_site_id, period_start, period_end):
        return self._events_by_site.get(noise_site_id)


def _raw_events_df(noise_site_id, timestamps):
    rows = []
    for ts in timestamps:
        rows.append(
            {
                "date_time": ts,
                "Leq": 50.0,
                "L90": 48.0,
                "80Hz": 30.0,
                "100Hz": 35.0,
                "125Hz": 31.0,
                "160Hz": 28.0,
                "200Hz": 33.0,
                "250Hz": 29.0,
                "Wind": 1.0,
                "Dir": 180,
                "Rain": 0.0,
                "Leq900": LEQ900_SAMPLE,
            }
        )
    df = pd.DataFrame(rows).set_index("date_time")
    df["noise_site_id"] = noise_site_id
    return df


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def test_collect_new_readings_skips_ignored_and_unknown_sites(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        client = FakeClient(
            sites=[
                {"noise_site_id": IGNORED_SITE, "site_id": 1},
                {"noise_site_id": UNKNOWN_SITE, "site_id": 2},
            ],
            events_by_site={},
        )

        summary = ingestion_job.collect_new_readings(client=client)

        assert IGNORED_SITE not in summary  # silently skipped, not even reported
        assert summary[UNKNOWN_SITE]["skipped"] == "site not known locally"


def test_collect_new_readings_persists_readings_and_processed_readings(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        timestamps = [
            pd.Timestamp("2025-01-01T23:00:00"),  # night -> survives processing filters
            pd.Timestamp("2025-01-01T12:00:00"),  # daytime -> dropped by processing filters
        ]
        client = FakeClient(
            sites=[{"noise_site_id": KNOWN_SITE, "site_id": 10}],
            events_by_site={KNOWN_SITE: _raw_events_df(KNOWN_SITE, timestamps)},
        )

        # AUTO_SEED_DATA also seeds demo ProcessedReading rows for this site (from
        # Slice C's synthetic fixture, all implicitly tagged detection_logic=
        # "original" via the model default) - compare against per-tag baselines
        # instead of absolute counts.
        processed_before = ProcessedReading.query.filter_by(noise_site_id=KNOWN_SITE).count()
        original_before = ProcessedReading.query.filter_by(
            noise_site_id=KNOWN_SITE, detection_logic="original"
        ).count()
        updated_2026_before = ProcessedReading.query.filter_by(
            noise_site_id=KNOWN_SITE, detection_logic="updated_2026"
        ).count()

        summary = ingestion_job.collect_new_readings(client=client)

        # The one surviving night-time, low-wind, low-rain reading passes both
        # detection logics' filters, so each writes its own tagged row.
        assert summary[KNOWN_SITE] == {
            "readings": 2,
            "processed_readings_original": 1,
            "processed_readings_updated_2026": 1,
        }
        assert Reading.query.filter_by(noise_site_id=KNOWN_SITE).count() == 2
        assert (
            ProcessedReading.query.filter_by(noise_site_id=KNOWN_SITE).count()
            == processed_before + 2
        )
        assert (
            ProcessedReading.query.filter_by(
                noise_site_id=KNOWN_SITE, detection_logic="original"
            ).count()
            == original_before + 1
        )
        assert (
            ProcessedReading.query.filter_by(
                noise_site_id=KNOWN_SITE, detection_logic="updated_2026"
            ).count()
            == updated_2026_before + 1
        )

        # leq_rmse wiring check: confirms a real value (computed from the raw
        # Leq900 sample via calculate_leq_rmse) flows through to both the raw
        # Reading row and the updated_2026 ProcessedReading row - the
        # "original"-tagged row correctly never carries one, by design (its
        # own PROCESSED_READING_COLUMNS has no such field, independent of
        # whether a real value was computed - see processing_service_updated_2026.py).
        expected_rmse = processing_service.calculate_leq_rmse({"leq900": LEQ900_SAMPLE})
        assert expected_rmse is not None  # sanity check on the fixture itself

        reading = Reading.query.filter_by(noise_site_id=KNOWN_SITE).first()
        assert float(reading.leq_rmse) == pytest.approx(expected_rmse, abs=0.01)
        updated_2026_row = ProcessedReading.query.filter_by(
            noise_site_id=KNOWN_SITE, detection_logic="updated_2026"
        ).first()
        assert float(updated_2026_row.leq_rmse) == pytest.approx(expected_rmse, abs=0.01)
        original_row = ProcessedReading.query.filter_by(
            noise_site_id=KNOWN_SITE, detection_logic="original"
        ).first()
        assert original_row.leq_rmse is None


def test_collect_new_readings_site_ids_scopes_to_named_sites_only(tmp_path, monkeypatch):
    # Mirrors the external-DB testing use case: the local `site` table can have
    # many known, non-ignored sites, but a real run should be limitable to just
    # the ones named via site_ids - everything else is silently skipped, the
    # same way an ignored/unknown site is (not even reported in the summary).
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        timestamps = [pd.Timestamp("2025-01-01T23:00:00")]
        client = FakeClient(
            sites=[
                {"noise_site_id": KNOWN_SITE, "site_id": 10},
                {"noise_site_id": OTHER_KNOWN_SITE, "site_id": 11},
            ],
            events_by_site={
                KNOWN_SITE: _raw_events_df(KNOWN_SITE, timestamps),
                OTHER_KNOWN_SITE: _raw_events_df(OTHER_KNOWN_SITE, timestamps),
            },
        )

        summary = ingestion_job.collect_new_readings(client=client, site_ids=[KNOWN_SITE])

        assert KNOWN_SITE in summary
        assert OTHER_KNOWN_SITE not in summary


def test_collect_new_readings_site_ids_none_keeps_default_behaviour(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        client = FakeClient(
            sites=[{"noise_site_id": KNOWN_SITE, "site_id": 10}],
            events_by_site={},
        )

        summary = ingestion_job.collect_new_readings(client=client, site_ids=None)

        assert KNOWN_SITE in summary


def test_collect_new_readings_is_idempotent_for_readings_on_rerun(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        timestamps = [pd.Timestamp("2025-01-01T23:00:00")]
        client = FakeClient(
            sites=[{"noise_site_id": KNOWN_SITE, "site_id": 10}],
            events_by_site={KNOWN_SITE: _raw_events_df(KNOWN_SITE, timestamps)},
        )

        ingestion_job.collect_new_readings(client=client)
        # simulate a re-run that overlaps the same fetch window (e.g. a retry) -
        # this used to raise an IntegrityError on the Reading PK in the old app.
        ingestion_job.collect_new_readings(client=client)

        assert Reading.query.filter_by(noise_site_id=KNOWN_SITE).count() == 1
