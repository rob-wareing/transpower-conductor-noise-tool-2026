"""One-off / repeatable: (re)generate the monthly_rainfall table from the
current reading table's full history.

For each site, groups the site's full raw reading history by calendar month
(1-12, climatological - not tied to a year, so every year's January combines
into one row) and computes sample_count + average rain_mm per month, via a
single set-based GROUP BY query (see ReadingRepository.aggregate_monthly_rainfall)
rather than pulling raw rows into pandas - reading is a ~2.4M-row table, far
too large for the per-row-into-DataFrame pattern generate_conductor_summary.py/
generate_rain_rate_fits.py use against the much smaller processed_reading
table. Excludes NULL rain_mm and rain_mm >= 99 (see
ReadingRepository.MAX_PLAUSIBLE_RAIN_MM - reading's ingestion-time
invalid-value sentinel is 99.9).

monthly_rainfall is a fully-derived/materialized table - every run replaces
its entire contents from scratch (see MonthlyRainfallRepository.replace_all).
A month with zero qualifying readings for a site (e.g. a site that came
online mid-year) gets no row. Intended to be re-run weekly via cron (see
DEPLOY.md's "Weekly derived-table regeneration" section) since reading
changes daily via ingestion.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_monthly_rainfall.py [--dry-run]
"""

import argparse
from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_repository import (
    ReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_rainfall_repository import (
    MonthlyRainfallRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned rows, don't write them"
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        records = ReadingRepository().aggregate_monthly_rainfall()

        if not records:
            print("No reading rows have rain_mm - nothing to summarize.")
            return

        for record in sorted(records, key=lambda r: (r["noise_site_id"], r["month"])):
            print(
                f"site={record['noise_site_id']} month={record['month']}: "
                f"n={record['sample_count']}, avg_rain_mm={record['avg_rain_mm']}"
            )

        if args.dry_run:
            print(f"\nWould write {len(records)} monthly_rainfall rows.")
            return

        computed_at = datetime.now()
        for record in records:
            record["computed_at"] = computed_at

        written = MonthlyRainfallRepository().replace_all(records)
        print(f"\nWrote {written} monthly_rainfall rows.")


if __name__ == "__main__":
    main()
