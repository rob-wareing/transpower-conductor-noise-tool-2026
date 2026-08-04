from sqlalchemy import func
from sqlalchemy.orm import aliased

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
    DEFAULT_PER_SITE_LIMIT = 3_000

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

    def find_by_id(self, reading_id):
        return db.session.get(ProcessedReading, reading_id)

    def save(self, reading):
        db.session.commit()
        return reading
