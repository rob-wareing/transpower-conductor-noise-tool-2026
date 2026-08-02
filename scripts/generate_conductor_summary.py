"""One-off / repeatable: (re)generate the conductor_summary table from the
current processed_reading data.

For each site and each detection_logic separately ("original" and
"updated_2026" always get their own row, never blended), computes
mean/max/min/median/lower-quartile/upper-quartile over L90, tone_100hz, and
tone_200hz (see backend/domain/trends_service.py::summarize_conductor_readings
for the actual stats logic), using only processed_reading rows where
include=1, is_wet=1, and measurement_duration_minutes=15.

conductor_summary is a fully-derived/materialized table - every run replaces
its entire contents from scratch (see
ConductorSummaryRepository.replace_all), it is never incrementally patched.
A site+detection_logic combination with zero matching rows today simply gets
no row (not a row of NULLs) - if it previously had one from an earlier run,
that stale row is removed too, since the whole table is replaced each time.

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
        readings = processed_reading_repository.list_readings(
            is_wet=True, measurement_duration_minutes=15, include=True
        )

        if not readings:
            print(
                "No processed_reading rows match include=1/is_wet=1/"
                "measurement_duration_minutes=15 - nothing to summarize."
            )
            return

        df = pd.DataFrame([_reading_to_row(r) for r in readings])
        summary_df = trends_service.summarize_conductor_readings(df)
        computed_at = datetime.now()

        for _, row in summary_df.sort_values(["noise_site_id", "detection_logic"]).iterrows():
            print(
                f"site={int(row['noise_site_id'])} detection_logic={row['detection_logic']!r}: "
                f"{int(row['sample_count'])} matching readings"
            )

        if args.dry_run:
            print(f"\nWould write {len(summary_df)} conductor_summary rows.")
            return

        records = summary_df.to_dict("records")
        for record in records:
            record["noise_site_id"] = int(record["noise_site_id"])
            record["sample_count"] = int(record["sample_count"])
            record["computed_at"] = computed_at

        conductor_summary_repository = ConductorSummaryRepository()
        written = conductor_summary_repository.replace_all(records)
        print(f"\nWrote {written} conductor_summary rows.")


if __name__ == "__main__":
    main()
