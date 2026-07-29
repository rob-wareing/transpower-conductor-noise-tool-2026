from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading import Reading


class ReadingRepository:
    def latest_datetime(self, noise_site_id):
        row = (
            Reading.query.filter_by(noise_site_id=noise_site_id)
            .order_by(Reading.datetime.desc())
            .first()
        )
        return row.datetime if row else None

    def upsert_readings(self, readings):
        # merge() keys off the (noise_site_id, datetime) primary key, so re-running
        # ingestion over an overlapping window updates existing rows instead of
        # raising an IntegrityError like the old app's plain append-only insert did.
        for reading in readings:
            db.session.merge(reading)
        db.session.commit()
        return len(readings)
