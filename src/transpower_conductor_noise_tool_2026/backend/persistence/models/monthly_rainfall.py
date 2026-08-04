from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per (noise_site_id, month) - climatological, month is 1-12 and not
# tied to a year (an average across every year of history). See
# backend/persistence/repositories/reading_repository.py::aggregate_monthly_rainfall
# for how these stats are computed and scripts/generate_monthly_rainfall.py
# for how this table is (re)generated from the raw reading table. A month
# only exists once at least one matching reading row does - a site that came
# online mid-year has no rows for the months before it started.


class MonthlyRainfall(db.Model):
    __tablename__ = "monthly_rainfall"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, primary_key=True)

    avg_rain_mm = db.Column(db.Numeric(4, 2), nullable=False)
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
