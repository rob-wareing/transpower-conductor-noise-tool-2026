from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per (noise_site_id, year, month) - min/max/avg rainfall and wind
# speed for that single calendar month. See
# backend/persistence/repositories/reading_repository.py::aggregate_monthly_weather_stats
# for how these stats are computed and scripts/generate_monthly_weather_stats.py
# for how this table is (re)generated from the raw reading table. sample_count
# is the total reading row count for the (site, year, month) bucket
# regardless of which fields are populated; the rain_mm/wind_speed columns
# are nullable independently of each other and of sample_count, since a
# bucket can have readings with one field present and the other missing or
# implausible.


class MonthlyWeatherStats(db.Model):
    __tablename__ = "monthly_weather_stats"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, primary_key=True)

    min_rain_mm = db.Column(db.Numeric(4, 2), nullable=True)
    max_rain_mm = db.Column(db.Numeric(4, 2), nullable=True)
    avg_rain_mm = db.Column(db.Numeric(4, 2), nullable=True)
    min_wind_speed = db.Column(db.Numeric(4, 1), nullable=True)
    max_wind_speed = db.Column(db.Numeric(4, 1), nullable=True)
    avg_wind_speed = db.Column(db.Numeric(4, 1), nullable=True)
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
