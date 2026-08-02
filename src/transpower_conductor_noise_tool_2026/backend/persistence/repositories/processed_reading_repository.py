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

    def list_readings(
        self,
        site_ids=None,
        start_datetime=None,
        end_datetime=None,
        is_wet=None,
        measurement_duration_minutes=None,
        detection_logic=None,
        include=None,
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

        return query.order_by(
            ProcessedReading.noise_site_id.asc(), ProcessedReading.datetime.asc()
        ).all()

    def find_by_id(self, reading_id):
        return db.session.get(ProcessedReading, reading_id)

    def save(self, reading):
        db.session.commit()
        return reading
