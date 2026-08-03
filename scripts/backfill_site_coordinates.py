"""One-off / repeatable: backfill the `site.latitude`/`site.longitude`
columns from data/site_locations.csv, matched by noise_site_id.

data/site_locations.csv is a manually-curated real-coordinates fixture
(columns "Site ID", "lon", "lat" - not the same shape as data/site.csv, which
carries no coordinate columns) covering a growing subset of the real sites
(currently the external MySQL fork's site table; some ids also overlap the
local demo fixture's 20 sites). Only ever UPDATEs rows that already exist
(matched by noise_site_id) - never inserts/deletes rows, and never touches
any other column. Site ids present in the CSV but not in whatever database
DATABASE_URL points at are reported, not treated as an error.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/backfill_site_coordinates.py [--dry-run]
"""

import argparse
import csv

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)

CSV_PATH = "data/site_locations.csv"


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
                noise_site_id = int(row["Site ID"])
                latitude = float(row["lat"]) if row["lat"].strip() else None
                longitude = float(row["lon"]) if row["lon"].strip() else None

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
