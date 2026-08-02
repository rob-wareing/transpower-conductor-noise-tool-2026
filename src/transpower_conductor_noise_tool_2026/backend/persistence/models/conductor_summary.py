from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per (noise_site_id, detection_logic, measurement_duration_minutes) -
# see backend/domain/trends_service.py::summarize_conductor_readings for how
# these stats are computed and scripts/generate_conductor_summary.py for how
# this table is (re)generated from processed_reading. A row only exists once
# at least one matching processed_reading row does, so every stat column is
# always a real computed value, never NULL.


class ConductorSummary(db.Model):
    __tablename__ = "conductor_summary"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    detection_logic = db.Column(db.String(20), primary_key=True)
    measurement_duration_minutes = db.Column(db.Integer, primary_key=True, default=15)

    l90_mean = db.Column(db.Numeric(6, 2), nullable=False)
    l90_max = db.Column(db.Numeric(6, 2), nullable=False)
    l90_min = db.Column(db.Numeric(6, 2), nullable=False)
    l90_median = db.Column(db.Numeric(6, 2), nullable=False)
    l90_q1 = db.Column(db.Numeric(6, 2), nullable=False)
    l90_q3 = db.Column(db.Numeric(6, 2), nullable=False)

    tone_100hz_mean = db.Column(db.Numeric(6, 2), nullable=False)
    tone_100hz_max = db.Column(db.Numeric(6, 2), nullable=False)
    tone_100hz_min = db.Column(db.Numeric(6, 2), nullable=False)
    tone_100hz_median = db.Column(db.Numeric(6, 2), nullable=False)
    tone_100hz_q1 = db.Column(db.Numeric(6, 2), nullable=False)
    tone_100hz_q3 = db.Column(db.Numeric(6, 2), nullable=False)

    tone_200hz_mean = db.Column(db.Numeric(6, 2), nullable=False)
    tone_200hz_max = db.Column(db.Numeric(6, 2), nullable=False)
    tone_200hz_min = db.Column(db.Numeric(6, 2), nullable=False)
    tone_200hz_median = db.Column(db.Numeric(6, 2), nullable=False)
    tone_200hz_q1 = db.Column(db.Numeric(6, 2), nullable=False)
    tone_200hz_q3 = db.Column(db.Numeric(6, 2), nullable=False)

    sample_count = db.Column(db.Integer, nullable=False)
    computed_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
