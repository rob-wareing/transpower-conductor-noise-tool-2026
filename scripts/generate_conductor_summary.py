"""One-off / repeatable: (re)generate the conductor_summary table from the
current processed_reading data.

For each site, each detection_logic, and each measurement_duration_minutes
separately ("original"/"updated_2026" and 1-minute/15-minute readings are
never blended together - every distinct combination gets its own row),
computes mean/max/min/median/lower-quartile/upper-quartile over L90,
tone_100hz, and tone_200hz (see
backend/domain/trends_service.py::summarize_conductor_readings for the actual
stats logic), using only processed_reading rows where include=1 and is_wet=1.

conductor_summary is a fully-derived/materialized table - every run replaces
its entire contents from scratch (see
ConductorSummaryRepository.replace_all), it is never incrementally patched.
A site+detection_logic+duration combination with zero matching rows today
simply gets no row (not a row of NULLs) - if it previously had one from an
earlier run, that stale row is removed too, since the whole table is
replaced each time.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_conductor_summary.py [--dry-run]
"""

import argparse
from datetime import datetime

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import trends_service
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_summary_repository import (
    ConductorSummaryRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)


def _reading_to_row(reading):
    return {
        "noise_site_id": reading.noise_site_id,
        "detection_logic": reading.detection_logic,
        "measurement_duration_minutes": reading.measurement_duration_minutes,
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
        readings = processed_reading_repository.list_readings(
            is_wet=True, include=True, per_site_limit=None
        )

        if not readings:
            print("No processed_reading rows match include=1/is_wet=1 - nothing to summarize.")
            return

        df = pd.DataFrame([_reading_to_row(r) for r in readings])
        summary_df = trends_service.summarize_conductor_readings(df)
        computed_at = datetime.now()

        sort_cols = ["noise_site_id", "detection_logic", "measurement_duration_minutes"]
        for _, row in summary_df.sort_values(sort_cols).iterrows():
            print(
                f"site={int(row['noise_site_id'])} detection_logic={row['detection_logic']!r} "
                f"measurement_duration_minutes={int(row['measurement_duration_minutes'])}: "
                f"{int(row['sample_count'])} matching readings"
            )

        if args.dry_run:
            print(f"\nWould write {len(summary_df)} conductor_summary rows.")
            return

        records = summary_df.to_dict("records")
        for record in records:
            record["noise_site_id"] = int(record["noise_site_id"])
            record["measurement_duration_minutes"] = int(record["measurement_duration_minutes"])
            record["sample_count"] = int(record["sample_count"])
            record["computed_at"] = computed_at

        conductor_summary_repository = ConductorSummaryRepository()
        written = conductor_summary_repository.replace_all(records)
        print(f"\nWrote {written} conductor_summary rows.")


if __name__ == "__main__":
    main()
