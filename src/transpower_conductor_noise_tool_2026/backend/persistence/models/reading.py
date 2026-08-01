from transpower_conductor_noise_tool_2026.backend.extensions import db


class Reading(db.Model):
    __tablename__ = "reading"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, primary_key=True)

    leq = db.Column(db.Numeric(4, 1), nullable=False)
    l90 = db.Column(db.Numeric(4, 1), nullable=False)
    leq_80hz = db.Column(db.Numeric(4, 1), nullable=False)
    leq_100hz = db.Column(db.Numeric(4, 1), nullable=False)
    leq_125hz = db.Column(db.Numeric(4, 1), nullable=False)
    leq_160hz = db.Column(db.Numeric(4, 1), nullable=False)
    leq_200hz = db.Column(db.Numeric(4, 1), nullable=False)
    leq_250hz = db.Column(db.Numeric(4, 1), nullable=False)

    wind_speed = db.Column(db.Numeric(4, 1), nullable=True)
    wind_direction = db.Column(db.Integer, nullable=True)
    rain_mm = db.Column(db.Numeric(3, 1), nullable=True)

    measurement_duration_minutes = db.Column(db.Integer, nullable=False, default=15)
    # RMSE of Leq for the period - a straight-line fit between the NW API's
    # Leq900 1-second series and time, root-mean-squared over the fit's
    # residuals (see processing_service.calculate_leq_rmse). NULL if the
    # period's Leq900 data was missing or too sparse to fit meaningfully.
    # See processing_service_updated_2026.py, the only thing that reads it.
    leq_rmse = db.Column(db.Numeric(5, 2), nullable=True)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
