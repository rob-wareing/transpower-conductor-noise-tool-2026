from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per (noise_site_id, year, month) - year+month, not climatological
# (a single calendar month is not collapsed across years). See
# backend/persistence/repositories/reading_repository.py::aggregate_monthly_rainfall
# for how these stats are computed and scripts/generate_monthly_rainfall.py
# for how this table is (re)generated from the raw reading table. A
# (year, month) only exists once at least one matching reading row does - a
# site that came online mid-year has no rows for the months before it
# started. Kept at this granularity rather than pre-collapsed so a date
# range can be re-aggregated on the fly (see
# site_climate_service.get_monthly_rainfall) without re-querying the raw
# reading table.


class MonthlyRainfall(db.Model):
    __tablename__ = "monthly_rainfall"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, primary_key=True)

    avg_rain_mm = db.Column(db.Numeric(4, 2), nullable=False)
    # Cumulative sum of rain_mm across every reading in this (site, year,
    # month) bucket - i.e. the total rainfall recorded during that single
    # calendar month. Bigger precision than avg_rain_mm to leave headroom
    # for an unusually wet month's total to run past the 4-digit range a
    # single reading or an average would.
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
