"""One-off: load real leq_rmse values from a local SQLite export into the
online (external MySQL fork) reading.leq_rmse column.

Source: a local SQLite file (path given on the command line, e.g.
../local_data/db_3.sqlite - outside this repo, machine-local) with a
`noise_weather_exported` table carrying `site_id`, `date_time`, `rmse`
columns among many others. `site_id` there matches this repo's
`reading.noise_site_id` directly (confirmed against real values - 115, 137,
142, etc. all appear in both), and `date_time` matches `reading.datetime`
(same 'YYYY-MM-DD HH:MM:SS' shape). Matched rows get their `reading.leq_rmse`
set to the source `rmse` value; unmatched source rows (no corresponding
`reading` row - a different site or datetime than what's stored) and
unmatched `reading` rows (no RMSE data available yet) are both left alone.

Deliberately NOT a per-row ORM read/write loop, unlike this repo's other
one-off scripts - the source table is ~2.8M rows and `reading` is ~2.4M rows,
and the "Updated 2026" backfill script's earlier real crashes
("Lost connection to MySQL server during query", see CLAUDE.md) showed that a
single long-lived connection doing many thousands of individual round trips
against this managed MySQL instance is unreliable at this scale. Instead:
  1. bulk-loads the source rows (site_id, date_time, rmse) into a session-
     scoped MySQL TEMPORARY TABLE, chunked into reasonably sized multi-row
     INSERTs (fast - a handful of round trips, not millions)
  2. runs one set-based `UPDATE reading JOIN tmp_leq_rmse ...` to apply all
     matches at once, using `reading`'s own (noise_site_id, datetime) primary
     key for the join
Everything happens on a single explicit Core connection/transaction (not
Flask-SQLAlchemy's scoped session) so the TEMPORARY TABLE - which only lives
for the connection that created it - is guaranteed to still be visible when
the final UPDATE runs.

Rows with an all-zero date_time ('0000-00-00 00:00:00', a small number of
garbage/placeholder rows in the source) are skipped - not a valid DATETIME
value under normal SQL modes and can never match a real reading.datetime
anyway.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/import_leq_rmse_from_sqlite.py <path-to-sqlite-file> [--dry-run] [--chunk-size N]
"""

import argparse
import sqlite3

import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db

SOURCE_TABLE = "noise_weather_exported"
DEFAULT_CHUNK_SIZE = 5000
ZERO_DATETIME = "0000-00-00 00:00:00"


def _iter_source_chunks(sqlite_path, chunk_size):
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT site_id, date_time, rmse FROM {SOURCE_TABLE} "
            f"WHERE rmse IS NOT NULL AND date_time != ?",
            (ZERO_DATETIME,),
        )
        while True:
            rows = cur.fetchmany(chunk_size)
            if not rows:
                return
            yield [
                {"noise_site_id": site_id, "datetime": date_time, "leq_rmse": rmse}
                for site_id, date_time, rmse in rows
            ]
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", help="Path to the local SQLite export (e.g. db_3.sqlite)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Load into the temp table and report match counts, don't UPDATE"
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        # A single explicit Core connection/transaction, not db.session - the
        # TEMPORARY TABLE below only lives for the connection that created it,
        # and db.session's scoped-session connection lifecycle isn't a
        # reliable guarantee that later statements reuse the same one.
        with db.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TEMPORARY TABLE tmp_leq_rmse ("
                    "noise_site_id INT NOT NULL, "
                    "datetime DATETIME NOT NULL, "
                    "leq_rmse DECIMAL(5,2) NOT NULL, "
                    "PRIMARY KEY (noise_site_id, datetime))"
                )
            )

            loaded = 0
            skipped_duplicate_or_out_of_range = 0
            for chunk in _iter_source_chunks(args.sqlite_path, args.chunk_size):
                result = connection.execute(
                    sa.text(
                        "INSERT IGNORE INTO tmp_leq_rmse (noise_site_id, datetime, leq_rmse) "
                        "VALUES (:noise_site_id, :datetime, :leq_rmse)"
                    ),
                    chunk,
                )
                # INSERT IGNORE silently drops duplicate (noise_site_id, datetime)
                # keys within the source and rows where leq_rmse doesn't fit
                # DECIMAL(5,2) - rowcount tells us how many of this chunk actually landed.
                loaded += result.rowcount
                skipped_duplicate_or_out_of_range += len(chunk) - result.rowcount
                print(f"loaded {loaded} rows into tmp_leq_rmse so far...", end="\r")

            print(f"\nLoaded {loaded} rows into tmp_leq_rmse "
                  f"({skipped_duplicate_or_out_of_range} skipped: duplicate key or out of DECIMAL(5,2) range).")

            match_count = connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM reading r "
                    "JOIN tmp_leq_rmse t ON r.noise_site_id = t.noise_site_id AND r.datetime = t.datetime"
                )
            ).scalar()
            print(f"{match_count} of those rows match an existing reading row (by noise_site_id + datetime).")

            if args.dry_run:
                print("--dry-run: temp table discarded, no UPDATE run.")
                return

            result = connection.execute(
                sa.text(
                    "UPDATE reading r "
                    "JOIN tmp_leq_rmse t ON r.noise_site_id = t.noise_site_id AND r.datetime = t.datetime "
                    "SET r.leq_rmse = t.leq_rmse"
                )
            )
            print(f"Updated {result.rowcount} reading rows with real leq_rmse values.")


if __name__ == "__main__":
    main()
