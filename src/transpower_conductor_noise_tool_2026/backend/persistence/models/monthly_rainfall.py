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
    # Cumulative sum of rain_mm across every reading in this (site, month)
    # bucket - i.e. the total rainfall recorded during that calendar month
    # across the site's full history, not a single year's total. Bigger
    # precision than avg_rain_mm since a sum over years of readings can run
    # well past the 4-digit range a single reading or an average would.
    total_rain = db.Column(db.Numeric(8, 2), nullable=False)
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
