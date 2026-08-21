import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading_availability import (
    ReadingAvailability,
)


class ReadingAvailabilityRepository:
    def list_all(self):
        return ReadingAvailability.query.order_by(ReadingAvailability.noise_site_id.asc()).all()

    def replace_all(self, records):
        # One row per site, always fully regenerated - a site with zero
        # processed_reading rows correctly has no row here, not a stale one.
        table = ReadingAvailability.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
