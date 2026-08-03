"""One-off / repeatable: (re)generate the rain_rate_fit table from the
current processed_reading data.

For each site, each detection_logic, and each metric (L90, tone_100hz,
tone_200hz) separately, fits metric = slope*ln(rain1) + intercept over
processed_reading rows where include=1, is_wet=1, and rain1 > 0 (see
backend/domain/trends_service.py::compute_rain_rate_fits for the actual fit
logic). A site/detection_logic/metric combination with fewer than 3
qualifying rows gets no row.

rain_rate_fit is a fully-derived/materialized table - every run replaces its
entire contents from scratch (see RainRateFitRepository.replace_all), it is
never incrementally patched. This mirrors scripts/generate_conductor_summary.py
and, like that script, is meant to be re-run manually whenever
processed_reading changes materially - no scheduling infrastructure exists in
this repo.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/generate_rain_rate_fits.py [--dry-run]
"""

import argparse
from datetime import datetime

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import trends_service
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.rain_rate_fit_repository import (
    RainRateFitRepository,
)


def _reading_to_row(reading):
    return {
        "noise_site_id": reading.noise_site_id,
        "detection_logic": reading.detection_logic,
        "rain1": float(reading.rain1),
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
        readings = processed_reading_repository.list_readings(is_wet=True, include=True)

        if not readings:
            print("No processed_reading rows match include=1/is_wet=1 - nothing to fit.")
            return

        df = pd.DataFrame([_reading_to_row(r) for r in readings])
        records = trends_service.compute_rain_rate_fits(df)

        if not records:
            print("No site/detection_logic/metric combination had >= 3 rain1>0 rows.")
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
            print(f"\nWould write {len(records)} rain_rate_fit rows.")
            return

        for record in records:
            record["computed_at"] = computed_at

        rain_rate_fit_repository = RainRateFitRepository()
        written = rain_rate_fit_repository.replace_all(records)
        print(f"\nWrote {written} rain_rate_fit rows.")


if __name__ == "__main__":
    main()
