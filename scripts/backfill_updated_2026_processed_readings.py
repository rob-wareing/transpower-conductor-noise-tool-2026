"""One-off: compute "Updated 2026" detection-logic ProcessedReading rows for
every site's existing raw Reading history, and write them alongside the
existing "original"-tagged rows (never replacing them).

Built for the external MySQL fork (see CLAUDE.md): that database has ~2.4M
real Reading rows from earlier real ingestion testing this session, all of
which only ever produced "original"-tagged ProcessedReading rows so far,
since processing_service_updated_2026.py didn't exist yet. This re-runs the
new detection logic over each site's already-stored raw readings and inserts
the resulting rows tagged detection_logic="updated_2026".

Note: the local demo/dev database has NO raw Reading data at all (its demo
ProcessedReading rows come straight from data/processed_reading.csv, bypassing
Reading entirely) - running this locally will correctly report zero sites
processed. This script only does real work against a database that actually
has ingested Reading history.

A site already carrying "updated_2026" rows is skipped (reported, not
overwritten) unless --force, in which case its existing "updated_2026" rows
are deleted and regenerated (inserts are pure appends, so re-running without
--force would otherwise duplicate rows) - EXCEPT when every one of its
existing "updated_2026" rows has leq_rmse = NULL, which only happens if they
were generated before real leq_rmse data existed (calculate_leq_rmse always
returned None until scripts/import_leq_rmse_from_sqlite.py loaded real
values). That's treated as stale and auto-regenerated even without --force,
so real RMSE data actually gets used (both for the leq_rmse filter and the
copied-through processed_reading.leq_rmse value) without having to remember
to pass --force by hand for every previously-run site.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/backfill_updated_2026_processed_readings.py [--dry-run] [--force]
"""

import argparse

import pandas as pd
import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import processing_service
from transpower_conductor_noise_tool_2026.backend.domain import processing_service_updated_2026
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_repository import (
    ReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)

# How many rows go into a single bulk INSERT statement. A site's rows are
# still committed as one all-or-nothing unit (see the "existing" skip check
# below - it assumes a site is either fully done or not started at all), but
# a single multi-thousand-row Core bulk insert keeps each site's connection
# checkout short - the earlier row-by-row ORM `session.add()` loop kept a
# connection checked out for minutes on a large site, which is what triggered
# repeated "Lost connection to MySQL server during query" failures against
# the external fork's managed MySQL instance (a connection-age limit, not a
# transaction-size one - confirmed by two crashes at two different, arbitrary
# points partway through unrelated sites, both after several cumulative
# minutes of connection use).
BULK_INSERT_CHUNK_SIZE = 5000


def _reading_to_row(reading):
    return {
        "noise_site_id": reading.noise_site_id,
        "datetime": reading.datetime,
        "leq": float(reading.leq),
        "l90": float(reading.l90),
        "leq_80hz": float(reading.leq_80hz),
        "leq_100hz": float(reading.leq_100hz),
        "leq_125hz": float(reading.leq_125hz),
        "leq_160hz": float(reading.leq_160hz),
        "leq_200hz": float(reading.leq_200hz),
        "leq_250hz": float(reading.leq_250hz),
        "wind_speed": float(reading.wind_speed) if reading.wind_speed is not None else None,
        "wind_direction": reading.wind_direction,
        "rain_mm": float(reading.rain_mm) if reading.rain_mm is not None else None,
        "leq_rmse": float(reading.leq_rmse) if reading.leq_rmse is not None else None,
    }


def _processed_reading_dict(row, detection_logic):
    # Same field mapping as ingestion_job.py::_processed_reading_from_row, but
    # returns a plain dict for a Core bulk insert instead of an ORM object for
    # session.add() - see BULK_INSERT_CHUNK_SIZE above for why.
    return {
        "noise_site_id": int(row["noise_site_id"]),
        "datetime": row["datetime"],
        "l90": row["l90"],
        "tone_100hz": row["tone_100hz"],
        "tone_200hz": row["tone_200hz"],
        "rain1": row["rain1"],
        "rain2": row["rain2"],
        "is_wet": bool(row["is_wet"]),
        "include": bool(row["include"]),
        "detection_logic": detection_logic,
        # A DataFrame column mixing real leq_rmse floats with missing values
        # stores the missing ones as NaN, not None (pandas' standard float64
        # behaviour) - PyMySQL rejects float('nan') outright, so this must go
        # through clean_leq_rmse before it can be written.
        "leq_rmse": processing_service.clean_leq_rmse(row.get("leq_rmse")),
    }


def _is_stale(existing):
    # All-NULL leq_rmse across every existing row means they were generated
    # before real RMSE data existed for this site (see the module docstring) -
    # treat as needing a refresh even without --force. Any row with a real
    # (non-NULL) value means this site was already (re)generated after real
    # data landed, so it's left alone on a repeat run.
    return bool(existing) and all(row.leq_rmse is None for row in existing)


def _bulk_insert_processed_readings(records):
    table = ProcessedReading.__table__
    for start in range(0, len(records), BULK_INSERT_CHUNK_SIZE):
        chunk = records[start : start + BULK_INSERT_CHUNK_SIZE]
        db.session.execute(sa.insert(table), chunk)
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print planned inserts, don't write them")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and regenerate a site's existing updated_2026 rows instead of skipping it",
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        site_repository = SiteRepository()
        reading_repository = ReadingRepository()
        processed_reading_repository = ProcessedReadingRepository()

        total_inserted = 0
        for site in site_repository.list_sites():
            readings = reading_repository.list_readings(site.noise_site_id)
            if not readings:
                continue

            existing = processed_reading_repository.list_readings(
                site_ids=[site.noise_site_id], detection_logic="updated_2026"
            )
            stale = _is_stale(existing)
            if existing and not stale and not args.force:
                print(
                    f"site={site.noise_site_id} {site.site_name!r}: skipping, already has "
                    f"{len(existing)} up-to-date updated_2026 rows (use --force to regenerate anyway)"
                )
                continue
            if existing and stale and not args.force:
                print(
                    f"site={site.noise_site_id} {site.site_name!r}: existing {len(existing)} updated_2026 "
                    f"rows all predate real leq_rmse data - regenerating"
                )

            df = pd.DataFrame([_reading_to_row(r) for r in readings])
            cleaned = processing_service.clean_readings(df)
            processed_df = processing_service_updated_2026.process_readings(cleaned)

            print(
                f"site={site.noise_site_id} {site.site_name!r}: {len(readings)} raw readings -> "
                f"{len(processed_df)} updated_2026 processed readings"
            )

            if args.dry_run:
                total_inserted += len(processed_df)
                continue

            if existing:
                ProcessedReading.query.filter_by(
                    noise_site_id=site.noise_site_id, detection_logic="updated_2026"
                ).delete()
                db.session.commit()

            records = [
                _processed_reading_dict(row, "updated_2026")
                for _, row in processed_df.iterrows()
            ]
            _bulk_insert_processed_readings(records)
            total_inserted += len(records)

        print(f"\n{'Would insert' if args.dry_run else 'Inserted'} {total_inserted} updated_2026 rows total.")


if __name__ == "__main__":
    main()
