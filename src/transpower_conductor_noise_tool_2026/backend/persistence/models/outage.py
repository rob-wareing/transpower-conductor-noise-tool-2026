from transpower_conductor_noise_tool_2026.backend.extensions import db


class Outage(db.Model):
    __tablename__ = "outage"

    id = db.Column(db.Integer, primary_key=True)
    noise_site_id = db.Column(db.Integer, nullable=False)
    outage_type = db.Column(db.String(20), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.String(200), nullable=True)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"], ["site.noise_site_id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
        db.ForeignKeyConstraint(["outage_type"], ["outage_type.outage_type"]),
    )
