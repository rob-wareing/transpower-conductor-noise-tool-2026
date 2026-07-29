from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.outage import Outage


class OutageRepository:
    def list_outages(self):
        return Outage.query.order_by(Outage.start_datetime.desc()).all()

    def find_by_id(self, outage_id):
        return db.session.get(Outage, outage_id)

    def add(self, outage):
        db.session.add(outage)
        db.session.commit()
        return outage

    def save(self, outage):
        db.session.commit()
        return outage

    def delete(self, outage):
        db.session.delete(outage)
        db.session.commit()
