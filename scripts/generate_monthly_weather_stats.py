"""One-off / repeatable: (re)generate the monthly_weather_stats table from
the current reading table's full history.

For each site and each (year, month) of its history, computes sample_count
(every reading row in the bucket, regardless of which fields are present)
plus min/max/avg rain_mm and min/max/avg wind_speed (each computed only over
values that pass its own plausibility filter), via a single set-based
GROUP BY query (see ReadingRepository.aggregate_monthly_weather_stats)
rather than pulling raw rows into pandas - reading is a ~2.4M-row table, far
too large for the per-row-into-DataFrame pattern generate_conductor_summary.py/
generate_rain_rate_fits.py use against the much smaller processed_reading
table. Excludes NULL/implausible rain_mm and wind_speed per-metric (see
ReadingRepository.MAX_PLAUSIBLE_RAIN_MM/MAX_PLAUSIBLE_WIND_SPEED) without
excluding the whole reading row from sample_count.

monthly_weather_stats is a fully-derived/materialized table - every run
replaces its entire contents from scratch (see
MonthlyWeatherStatsRepository.replace_all). A (year, month) with zero
reading rows for a site gets no row. Intended to be re-run weekly via cron
(see DEPLOY.md's "Weekly derived-table regeneration" section) since reading
changes daily via ingestion.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_monthly_weather_stats.py [--dry-run]
"""

import argparse
from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_repository import (
    ReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_weather_stats_repository import (
    MonthlyWeatherStatsRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned rows, don't write them"
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        records = ReadingRepository().aggregate_monthly_weather_stats()

        if not records:
            print("No reading rows found - nothing to summarize.")
            return

        for record in sorted(records, key=lambda r: (r["noise_site_id"], r["year"], r["month"])):
            print(
                f"site={record['noise_site_id']} {record['year']}-{record['month']:02d}: "
                f"n={record['sample_count']}, "
                f"rain(min/avg/max)={record['min_rain_mm']}/{record['avg_rain_mm']}/{record['max_rain_mm']}, "
                f"wind(min/avg/max)={record['min_wind_speed']}/{record['avg_wind_speed']}/{record['max_wind_speed']}"
            )

        if args.dry_run:
            print(f"\nWould write {len(records)} monthly_weather_stats rows.")
            return

        computed_at = datetime.now()
        for record in records:
            record["computed_at"] = computed_at

        written = MonthlyWeatherStatsRepository().replace_all(records)
        print(f"\nWrote {written} monthly_weather_stats rows.")


if __name__ == "__main__":
    main()
