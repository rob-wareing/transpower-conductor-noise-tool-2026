"""One-off / repeatable: (re)generate the reading_availability table from the
current processed_reading table's full history.

For each site, computes the true min/max datetime and row count over its
*entire* processed_reading history via a single set-based GROUP BY query
(see ProcessedReadingRepository.aggregate_availability) - never capped by
per_site_limit and never filtered by date/condition/conductor/detection_logic,
since the whole point is a true, filter-independent picture of data
availability. Backs the Charts tab's "Data Availability Timeline"
(chart_service.py::get_availability_timeline), which is deliberately
decoupled from every other Charts tab option (site selection, date range,
condition, conductor/grease, detection_logic, show_historical) - it always
shows every active site's full history regardless of what's currently
selected elsewhere on the tab.

reading_availability is a fully-derived/materialized table - every run
replaces its entire contents from scratch (see
ReadingAvailabilityRepository.replace_all). A site with zero processed_reading
rows gets no row. Intended to be re-run daily via cron (see DEPLOY.md's daily
chain), since processed_reading grows daily via ingestion - unlike wind_rose/
monthly_rainfall's weekly cadence, which are sourced from the more slowly-
changing reading table.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_reading_availability.py [--dry-run]
"""

import argparse
from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_availability_repository import (
    ReadingAvailabilityRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned rows, don't write them"
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        records = ProcessedReadingRepository().aggregate_availability()

        if not records:
            print("No processed_reading rows - nothing to summarize.")
            return

        for record in sorted(records, key=lambda r: r["noise_site_id"]):
            print(
                f"site={record['noise_site_id']}: n={record['row_count']}, "
                f"min={record['min_datetime']}, max={record['max_datetime']}"
            )

        if args.dry_run:
            print(f"\nWould write {len(records)} reading_availability rows.")
            return

        computed_at = datetime.now()
        for record in records:
            record["computed_at"] = computed_at

        written = ReadingAvailabilityRepository().replace_all(records)
        print(f"\nWrote {written} reading_availability rows.")


if __name__ == "__main__":
    main()
