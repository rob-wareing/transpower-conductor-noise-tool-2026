from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.grease_description import (
    GreaseDescription,
)


class GreaseDescriptionRepository:
    def list_all(self):
        return GreaseDescription.query.order_by(GreaseDescription.grease.asc()).all()

    def add_all(self, records):
        for record in records:
            db.session.add(record)
        db.session.commit()
