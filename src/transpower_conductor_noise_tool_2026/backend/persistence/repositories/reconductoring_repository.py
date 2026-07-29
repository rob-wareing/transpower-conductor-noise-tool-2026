from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)


class ReconductoringRepository:
    def list_events(self):
        return Reconductoring.query.order_by(Reconductoring.reconductoring_date.desc()).all()

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
