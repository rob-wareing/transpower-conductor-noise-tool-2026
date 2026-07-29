from transpower_conductor_noise_tool_2026.backend.extensions import db


class OutageType(db.Model):
    __tablename__ = "outage_type"

    outage_type = db.Column(db.String(20), primary_key=True)
