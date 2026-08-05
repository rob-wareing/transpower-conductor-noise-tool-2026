"""Repeatable: (re)generate the conductor_age_fit table from the current
processed_reading data.

For each site, each detection_logic, and each metric (L90, tone_100hz,
tone_200hz) separately, fits metric = slope*ln(reconductoring_age) + intercept
over processed_reading rows where include=1 and reconductoring_age is not
NULL and > 0 (see backend/domain/trends_service.py::compute_conductor_age_fits
for the actual fit logic). A site/detection_logic/metric combination with
fewer than 3 qualifying rows gets no row.

reconductoring_age must be kept current first (see
scripts/calculate_reconductoring_age.py) - this script only reads it, it
never computes it.

conductor_age_fit is a fully-derived/materialized table - every run replaces
its entire contents from scratch (see ConductorAgeFitRepository.replace_all),
it is never incrementally patched. This mirrors
scripts/generate_rain_rate_fits.py and is re-run at the same cadence (daily,
via cron - see DEPLOY.md).

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_conductor_age_fits.py [--dry-run]
"""

import argparse
from datetime import datetime

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import trends_service
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_age_fit_repository import (
    ConductorAgeFitRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)


def _reading_to_row(reading):
    return {
        "noise_site_id": reading.noise_site_id,
        "detection_logic": reading.detection_logic,
        "reconductoring_age": reading.reconductoring_age,
        "l90": float(reading.l90),
        "tone_100hz": float(reading.tone_100hz),
        "tone_200hz": float(reading.tone_200hz),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned rows, don't write them"
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        processed_reading_repository = ProcessedReadingRepository()
        # Offline/cron batch job, not an interactive request - needs the
        # full history, not the per-request per-site cap.
        readings = [
            reading
            for reading in processed_reading_repository.list_readings(
                include=True, per_site_limit=None
            )
            if reading.reconductoring_age is not None
        ]

        if not readings:
            print("No processed_reading rows have a non-NULL reconductoring_age - nothing to fit.")
            return

        df = pd.DataFrame([_reading_to_row(r) for r in readings])
        records = trends_service.compute_conductor_age_fits(df)

        if not records:
            print("No site/detection_logic/metric combination had >= 3 rows with reconductoring_age > 0.")
            return

        computed_at = datetime.now()
        for record in sorted(
            records, key=lambda r: (r["noise_site_id"], r["detection_logic"], r["metric"])
        ):
            print(
                f"site={record['noise_site_id']} detection_logic={record['detection_logic']!r} "
                f"metric={record['metric']!r}: slope={record['slope']}, "
                f"intercept={record['intercept']}, r_squared={record['r_squared']}, "
                f"n={record['sample_count']}"
            )

        if args.dry_run:
            print(f"\nWould write {len(records)} conductor_age_fit rows.")
            return

        for record in records:
            record["computed_at"] = computed_at

        conductor_age_fit_repository = ConductorAgeFitRepository()
        written = conductor_age_fit_repository.replace_all(records)
        print(f"\nWrote {written} conductor_age_fit rows.")


if __name__ == "__main__":
    main()
