from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.outage_type import OutageType


class OutageTypeRepository:
    def list_types(self):
        return OutageType.query.order_by(OutageType.outage_type.asc()).all()

    def add_types(self, types):
        for outage_type in types:
            db.session.add(outage_type)
        db.session.commit()
