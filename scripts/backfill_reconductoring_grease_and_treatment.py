"""One-off: backfill the `grease`/`conductor_and_treatment` columns on the
`reconductoring` table from data/reconductoring_2026.csv, matched by `id`.

Built for the external MySQL fork (see CLAUDE.md / the external-DB test plan):
that server's `reconductoring` table predates a later schema change and was
missing `grease`/`conductor_and_treatment` entirely until they were added as
two new nullable columns. This fills in real values for the existing 42 rows
from the CSV (`Grease` -> grease, `SC proposed renaming` -> conductor_and_treatment)
rather than leaving them NULL, so the Reconductoring tab and the Charts tab's
conductor/grease filters display real data. Only ever UPDATEs rows that
already exist (matched by id) - never inserts/deletes rows.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/backfill_reconductoring_grease_and_treatment.py [--dry-run]
"""

import argparse
import csv

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)

CSV_PATH = "data/reconductoring_2026.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates, don't write them")
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        repository = ReconductoringRepository()

        updated, missing = 0, []
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                event_id = int(row["id"])
                grease = row["Grease"].strip() or None
                conductor_and_treatment = row["SC proposed renaming"].strip() or None

                event = repository.find_by_id(event_id)
                if event is None:
                    missing.append(event_id)
                    continue

                print(
                    f"id={event_id} site={event.noise_site_id}: "
                    f"grease {event.grease!r} -> {grease!r}, "
                    f"conductor_and_treatment {event.conductor_and_treatment!r} -> {conductor_and_treatment!r}"
                )
                if not args.dry_run:
                    event.grease = grease
                    event.conductor_and_treatment = conductor_and_treatment
                    repository.save(event)
                updated += 1

        print(f"\n{'Would update' if args.dry_run else 'Updated'} {updated} rows.")
        if missing:
            print(f"WARNING: {len(missing)} CSV ids had no matching row in the DB: {missing}")


if __name__ == "__main__":
    main()
