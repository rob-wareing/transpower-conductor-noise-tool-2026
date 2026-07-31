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
are deleted and regenerated (add_readings() is a pure append, so re-running
without --force would otherwise duplicate rows).

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/backfill_updated_2026_processed_readings.py [--dry-run] [--force]
"""

import argparse

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import processing_service
from transpower_conductor_noise_tool_2026.backend.domain import processing_service_updated_2026
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.ingestion.ingestion_job import (
    _processed_reading_from_row,
)
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
            if existing and not args.force:
                print(
                    f"site={site.noise_site_id} {site.site_name!r}: skipping, already has "
                    f"{len(existing)} updated_2026 rows (use --force to regenerate)"
                )
                continue

            df = pd.DataFrame([_reading_to_row(r) for r in readings])
            cleaned = processing_service.clean_readings(df)
            processed_df = processing_service_updated_2026.process_readings(cleaned)

            print(
                f"site={site.noise_site_id} {site.site_name!r}: {len(readings)} raw readings -> "
                f"{len(processed_df)} updated_2026 processed readings"
            )

            if args.dry_run:
                continue

            if existing:
                ProcessedReading.query.filter_by(
                    noise_site_id=site.noise_site_id, detection_logic="updated_2026"
                ).delete()
                db.session.commit()

            processed_readings = [
                _processed_reading_from_row(row, "updated_2026")
                for _, row in processed_df.iterrows()
            ]
            processed_reading_repository.add_readings(processed_readings)
            total_inserted += len(processed_readings)

        print(f"\n{'Would insert' if args.dry_run else 'Inserted'} {total_inserted} updated_2026 rows total.")


if __name__ == "__main__":
    main()
