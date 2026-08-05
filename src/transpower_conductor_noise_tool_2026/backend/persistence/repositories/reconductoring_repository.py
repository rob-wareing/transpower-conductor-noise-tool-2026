import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)


class ReconductoringRepository:
    def list_events(self):
        return Reconductoring.query.order_by(Reconductoring.reconductoring_date.desc()).all()

    def latest_by_site(self):
        # {noise_site_id: most recent reconductoring_date} - only sites with
        # at least one event appear; a site with no reconductoring history
        # has no entry at all, not a None value.
        rows = db.session.query(
            Reconductoring.noise_site_id,
            sa.func.max(Reconductoring.reconductoring_date),
        ).group_by(Reconductoring.noise_site_id).all()
        return dict(rows)

    def find_by_id(self, event_id):
        return db.session.get(Reconductoring, event_id)

    def add(self, event):
        db.session.add(event)
        db.session.commit()
        return event

    def save(self, event):
        db.session.commit()
        return event

    def delete(self, event):
        db.session.delete(event)
        db.session.commit()
