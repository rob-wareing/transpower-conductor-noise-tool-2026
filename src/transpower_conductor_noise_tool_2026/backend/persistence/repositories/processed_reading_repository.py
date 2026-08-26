from datetime import datetime

from sqlalchemy import bindparam, func
from sqlalchemy.orm import aliased

from transpower_conductor_noise_tool_2026.backend.config import Settings
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)


class ProcessedReadingRepository:
    def add_readings(self, readings):
        for reading in readings:
            db.session.add(reading)
        db.session.commit()
        return len(readings)

    # A flat LIMIT after ORDER BY noise_site_id, datetime always returns a
    # prefix of sites by id, silently dropping every site that sorts later -
    # not a random/fair truncation. per_site_limit instead caps each site
    # independently (keeping its most recent rows), so every site with data
    # is guaranteed some representation regardless of total row volume.
    # Tunable without a code change via the PER_SITE_READING_LIMIT env var
    # (see config.py) - e.g. raise it if a site's real history outgrows what
    # feels like enough for trend analysis.
    DEFAULT_PER_SITE_LIMIT = Settings.PER_SITE_READING_LIMIT

    def list_readings(
        self,
        site_ids=None,
        start_datetime=None,
        end_datetime=None,
        is_wet=None,
        measurement_duration_minutes=None,
        detection_logic=None,
        include=None,
        limit=None,
        per_site_limit=DEFAULT_PER_SITE_LIMIT,
    ):
        query = ProcessedReading.query

        if site_ids:
            query = query.filter(ProcessedReading.noise_site_id.in_(site_ids))
        if start_datetime:
            query = query.filter(ProcessedReading.datetime > start_datetime)
        if end_datetime:
            query = query.filter(ProcessedReading.datetime <= end_datetime)
        if is_wet is not None:
            query = query.filter(ProcessedReading.is_wet == is_wet)
        if measurement_duration_minutes is not None:
            query = query.filter(
                ProcessedReading.measurement_duration_minutes == measurement_duration_minutes
            )
        if detection_logic is not None:
            query = query.filter(ProcessedReading.detection_logic == detection_logic)
        if include is not None:
            query = query.filter(ProcessedReading.include == include)

        model = ProcessedReading
        if per_site_limit is not None:
            row_number = (
                func.row_number()
                .over(
                    partition_by=ProcessedReading.noise_site_id,
                    order_by=ProcessedReading.datetime.desc(),
                )
                .label("rn")
            )
            ranked = query.add_columns(row_number).subquery()
            model = aliased(ProcessedReading, ranked)
            query = db.session.query(model).filter(ranked.c.rn <= per_site_limit)

        query = query.order_by(model.noise_site_id.asc(), model.datetime.asc())
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def aggregate_availability(self):
        # One row per site: min/max/count over its *full* processed_reading
        # history - never capped by per_site_limit and never filtered by
        # date/condition/conductor/detection_logic, since the whole point of
        # reading_availability is a true, filter-independent picture of data
        # availability. SQL Core aggregation (not pandas), same reasoning as
        # ReadingRepository.aggregate_wind_rose.
        query = db.session.query(
            ProcessedReading.noise_site_id,
            func.min(ProcessedReading.datetime).label("min_datetime"),
            func.max(ProcessedReading.datetime).label("max_datetime"),
            func.count(ProcessedReading.id).label("row_count"),
        ).group_by(ProcessedReading.noise_site_id)

        return [
            {
                "noise_site_id": row.noise_site_id,
                "min_datetime": row.min_datetime,
                "max_datetime": row.max_datetime,
                "row_count": row.row_count,
            }
            for row in query.all()
        ]

    def count_by_detection_logic(self, noise_site_id, include=True):
        # {"original": N, "updated_2026": M} for one site - a detection_logic
        # value with zero qualifying rows is still present in the result as
        # 0, unlike the GROUP BY aggregates elsewhere in this repository,
        # since callers (the Locations tab's per-site summary) want both
        # counts every time, not just the ones that happen to be non-zero.
        query = db.session.query(
            ProcessedReading.detection_logic, func.count(ProcessedReading.id)
        ).filter(ProcessedReading.noise_site_id == noise_site_id)
        if include is not None:
            query = query.filter(ProcessedReading.include == include)
        counts = dict(query.group_by(ProcessedReading.detection_logic).all())
        return {
            "original": counts.get("original", 0),
            "updated_2026": counts.get("updated_2026", 0),
        }

    def find_by_id(self, reading_id):
        return db.session.get(ProcessedReading, reading_id)

    def save(self, reading):
        db.session.commit()
        return reading

    RECALCULATE_CHUNK_SIZE = 5_000

    def recalculate_reconductoring_ages(self, cutoffs_by_site, dry_run=False):
        # cutoffs_by_site: {noise_site_id: date} from
        # ReconductoringRepository.latest_by_site() - a site with no entry
        # has no reconductoring history, so every one of its rows gets NULL.
        # Every row is recomputed on every call, not just new ones - a new
        # reconductoring event can retroactively turn a previously-aged row
        # back to NULL (it now predates the site's *new* most recent
        # conductor), so this can't be done incrementally.
        site_ids = [row[0] for row in db.session.query(ProcessedReading.noise_site_id).distinct()]

        updates = []
        for noise_site_id in site_ids:
            cutoff_date = cutoffs_by_site.get(noise_site_id)
            cutoff_datetime = (
                datetime.combine(cutoff_date, datetime.min.time()) if cutoff_date else None
            )
            rows = (
                db.session.query(ProcessedReading.id, ProcessedReading.datetime)
                .filter(ProcessedReading.noise_site_id == noise_site_id)
                .all()
            )
            for row_id, row_datetime in rows:
                if cutoff_datetime is not None and row_datetime >= cutoff_datetime:
                    age = (row_datetime - cutoff_datetime).days
                else:
                    age = None
                updates.append({"_id": row_id, "_age": age})

        summary = {
            "total": len(updates),
            "aged": sum(1 for u in updates if u["_age"] is not None),
            "nulled": sum(1 for u in updates if u["_age"] is None),
        }

        if dry_run or not updates:
            return summary

        table = ProcessedReading.__table__
        stmt = (
            table.update()
            .where(table.c.id == bindparam("_id"))
            .values(reconductoring_age=bindparam("_age"))
        )
        for start in range(0, len(updates), self.RECALCULATE_CHUNK_SIZE):
            chunk = updates[start : start + self.RECALCULATE_CHUNK_SIZE]
            db.session.execute(stmt, chunk)
        db.session.commit()
        return summary
