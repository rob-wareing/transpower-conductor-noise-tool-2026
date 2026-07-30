import pandas as pd

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.ingestion import ingestion_job
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading import Reading

KNOWN_SITE = 115  # from data/site.csv, not in IGNORE_SITES
OTHER_KNOWN_SITE = 137  # from data/site.csv, not in IGNORE_SITES
IGNORED_SITE = 51  # in data/site.csv, but also in IGNORE_SITES
UNKNOWN_SITE = 9999  # not in data/site.csv at all


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
        # Slice C's synthetic fixture) - compare against a baseline instead of an
        # absolute count.
        processed_before = ProcessedReading.query.filter_by(noise_site_id=KNOWN_SITE).count()

        summary = ingestion_job.collect_new_readings(client=client)

        assert summary[KNOWN_SITE] == {"readings": 2, "processed_readings": 1}
        assert Reading.query.filter_by(noise_site_id=KNOWN_SITE).count() == 2
        assert (
            ProcessedReading.query.filter_by(noise_site_id=KNOWN_SITE).count()
            == processed_before + 1
        )


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
