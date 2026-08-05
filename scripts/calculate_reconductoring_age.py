"""Repeatable: (re)calculates processed_reading.reconductoring_age from each
site's most recent reconductoring event.

For every site with at least one reconductoring event, sets
reconductoring_age = (row.datetime - most_recent_event.reconductoring_date).days
for every processed_reading row at or after that date - i.e. how long the
*current* conductor has been in place when that row was measured. Every row
before the site's most recent event (measured under an older conductor - not
comparable to newer readings) is set to NULL, as is every row for a site
with no reconductoring history at all.

Every row is recomputed on every run, not just new ones - a new
reconductoring event moves the cutoff forward and can turn a previously-aged
row back to NULL, so this can't be done incrementally (see
ProcessedReadingRepository.recalculate_reconductoring_ages).

This must be re-run whenever processed_reading gains new rows (daily, via
ingestion) or reconductoring gains a new event, and before
generate_conductor_age_fits.py, since that fit is computed over this
column - see DEPLOY.md's daily cron jobs.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/calculate_reconductoring_age.py [--dry-run]
"""

import argparse

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the planned counts, don't write them"
    )
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        cutoffs = ReconductoringRepository().latest_by_site()
        if not cutoffs:
            print("No reconductoring events - every processed_reading row will be NULL.")
        else:
            for noise_site_id, cutoff_date in sorted(cutoffs.items()):
                print(f"site={noise_site_id}: most recent reconductoring={cutoff_date}")

        summary = ProcessedReadingRepository().recalculate_reconductoring_ages(
            cutoffs, dry_run=args.dry_run
        )
        verb = "Would recalculate" if args.dry_run else "Recalculated"
        print(
            f"\n{verb} reconductoring_age for {summary['total']} processed_reading rows "
            f"({summary['aged']} aged, {summary['nulled']} set to NULL)."
        )


if __name__ == "__main__":
    main()
