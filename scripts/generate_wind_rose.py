"""One-off / repeatable: (re)generate the wind_rose table from the current
reading table's full history.

For each site, groups the site's full raw reading history into 16 compass
sectors (22.5 degrees each, centered on N/NNE/.../NNW) and computes
sample_count + average wind_speed per sector, via a single set-based GROUP BY
query (see ReadingRepository.aggregate_wind_rose) rather than pulling raw
rows into pandas - reading is a ~2.4M-row table, far too large for the
per-row-into-DataFrame pattern generate_conductor_summary.py/
generate_rain_rate_fits.py use against the much smaller processed_reading
table. Excludes wind_speed >= 200 and NULL wind_direction/wind_speed (see
ReadingRepository.MAX_PLAUSIBLE_WIND_SPEED - reading's ingestion-time
invalid-value sentinel is 999.9, plus the odd sensor glitch above it).

wind_rose is a fully-derived/materialized table - every run replaces its
entire contents from scratch (see WindRoseRepository.replace_all). A sector
with zero qualifying readings for a site gets no row. Intended to be
re-run weekly via cron (see DEPLOY.md's "Weekly derived-table regeneration"
section) since reading changes daily via ingestion.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_wind_rose.py [--dry-run]
"""

import argparse
from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_repository import (
    ReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.wind_rose_repository import (
    WindRoseRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned rows, don't write them"
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        records = ReadingRepository().aggregate_wind_rose()

        if not records:
            print("No reading rows have both wind_speed and wind_direction - nothing to summarize.")
            return

        for record in sorted(records, key=lambda r: (r["noise_site_id"], r["direction_sector"])):
            print(
                f"site={record['noise_site_id']} sector={record['direction_sector']}: "
                f"n={record['sample_count']}, avg_wind_speed={record['avg_wind_speed']}"
            )

        if args.dry_run:
            print(f"\nWould write {len(records)} wind_rose rows.")
            return

        computed_at = datetime.now()
        for record in records:
            record["computed_at"] = computed_at

        written = WindRoseRepository().replace_all(records)
        print(f"\nWrote {written} wind_rose rows.")


if __name__ == "__main__":
    main()
