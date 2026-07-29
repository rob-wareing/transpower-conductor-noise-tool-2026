from transpower_conductor_noise_tool_2026.backend.extensions import db


class HistoricalResult(db.Model):
    __tablename__ = "historical_result"

    id = db.Column(db.Integer, primary_key=True)
    noise_site_id = db.Column(db.Integer, nullable=False)
    period_length = db.Column(db.Integer, nullable=False, default=2)
    period_end_date = db.Column(db.Date, nullable=False)
    leq_adj = db.Column(db.Numeric(4, 1), nullable=True)
    tone_100hz = db.Column(db.Numeric(4, 2), nullable=True)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"], ["site.noise_site_id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
    )
