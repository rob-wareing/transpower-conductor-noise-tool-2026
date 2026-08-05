from transpower_conductor_noise_tool_2026.backend.extensions import db


class ProcessedReading(db.Model):
    __tablename__ = "processed_reading"

    id = db.Column(db.Integer, primary_key=True)
    noise_site_id = db.Column(db.Integer, nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)

    l90 = db.Column(db.Numeric(4, 1), nullable=False)
    tone_100hz = db.Column(db.Numeric(4, 2), nullable=False)
    tone_200hz = db.Column(db.Numeric(4, 2), nullable=False)

    rain1 = db.Column(db.Numeric(3, 1), nullable=False)
    rain2 = db.Column(db.Numeric(3, 1), nullable=False)
    is_wet = db.Column(db.Boolean, nullable=False)
    include = db.Column(db.Boolean, nullable=False, default=True)
    measurement_duration_minutes = db.Column(db.Integer, nullable=False, default=15)
    detection_logic = db.Column(db.String(20), nullable=False, default="original")
    # Copied across from Reading.leq_rmse only for rows processed by the
    # updated_2026 detection logic (see processing_service_updated_2026.py) -
    # always NULL for "original"-tagged rows.
    leq_rmse = db.Column(db.Numeric(5, 2), nullable=True)
    # Days between this row's datetime and its site's most recent
    # reconductoring event, i.e. how long the *current* conductor has been in
    # place. NULL for rows that predate the site's latest reconductoring (an
    # older conductor - not comparable) or for sites with no reconductoring
    # history at all. See scripts/calculate_reconductoring_age.py /
    # ProcessedReadingRepository.recalculate_reconductoring_ages for how this
    # is (re)computed - it is not maintained at ingestion time.
    reconductoring_age = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
