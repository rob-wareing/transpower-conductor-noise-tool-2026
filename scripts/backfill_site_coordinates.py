"""One-off: backfill the `site.latitude`/`site.longitude` columns from
data/site.csv, matched by noise_site_id.

Built for the external MySQL fork (see CLAUDE.md / the external-DB test
plan): that server's real `site` table got the two new nullable
latitude/longitude columns added (migration 0008's DDL, applied by hand -
see CLAUDE.md), but every row's value is still NULL since nothing has ever
populated them there. This fills in real values from data/site.csv (this
repo's own demo fixture, which already carries approximate town-center
coordinates for the same site names/IDs the old app used) for whichever
noise_site_ids overlap. Only ever UPDATEs rows that already exist (matched
by noise_site_id) - never inserts/deletes rows, and never touches any other
column.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/backfill_site_coordinates.py [--dry-run]
"""

import argparse
import csv

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)

CSV_PATH = "data/site.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates, don't write them")
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        repository = SiteRepository()

        updated, missing = 0, []
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                noise_site_id = int(row["noise_site_id"])
                latitude = float(row["latitude"]) if row["latitude"].strip() else None
                longitude = float(row["longitude"]) if row["longitude"].strip() else None

                site = repository.find_by_noise_site_id(noise_site_id)
                if site is None:
                    missing.append(noise_site_id)
                    continue

                print(
                    f"noise_site_id={noise_site_id} {site.site_name!r}: "
                    f"latitude {site.latitude} -> {latitude}, longitude {site.longitude} -> {longitude}"
                )
                if not args.dry_run:
                    site.latitude = latitude
                    site.longitude = longitude
                    repository.save(site)
                updated += 1

        print(f"\n{'Would update' if args.dry_run else 'Updated'} {updated} rows.")
        if missing:
            print(
                f"NOTE: {len(missing)} CSV noise_site_ids had no matching row in the DB "
                f"(not in this database): {missing}"
            )


if __name__ == "__main__":
    main()
