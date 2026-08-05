from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per (noise_site_id, detection_logic, metric) - a precomputed
# logarithmic best-fit (metric = slope * ln(reconductoring_age) + intercept)
# over that site/detection_logic/metric's included processed_reading rows
# with a non-NULL reconductoring_age. See
# backend/domain/trends_service.py::compute_conductor_age_fits for how these
# are computed and scripts/generate_conductor_age_fits.py for how this table
# is (re)generated. A row only exists once at least 3 matching rows (with
# reconductoring_age > 0 - log undefined at 0) do, so slope/intercept are
# always real computed values, never NULL.


class ConductorAgeFit(db.Model):
    __tablename__ = "conductor_age_fit"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    detection_logic = db.Column(db.String(20), primary_key=True)
    metric = db.Column(db.String(20), primary_key=True)

    slope = db.Column(db.Numeric(10, 4), nullable=False)
    intercept = db.Column(db.Numeric(10, 4), nullable=False)
    r_squared = db.Column(db.Numeric(5, 4), nullable=True)
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
