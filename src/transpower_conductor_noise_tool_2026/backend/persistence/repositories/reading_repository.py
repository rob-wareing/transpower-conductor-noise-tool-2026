import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading import Reading

# The 16 compass sectors in index order, each 22.5 degrees wide and centered
# on its heading (N is [348.75, 11.25), NNE is [11.25, 33.75), etc.).
DIRECTION_SECTORS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


class ReadingRepository:
    # Both thresholds exclude reading's ingestion-time invalid-value
    # sentinels (processing_service.MAX_VALID_WIND_SPEED = 999.9,
    # MAX_VALID_RAIN_FALL = 99.9) plus any stray glitch values above them -
    # not real readings, and would otherwise skew the wind-rose/rainfall
    # averages.
    MAX_PLAUSIBLE_WIND_SPEED = 200
    MAX_PLAUSIBLE_RAIN_MM = 99

    def latest_datetime(self, noise_site_id):
        row = (
            Reading.query.filter_by(noise_site_id=noise_site_id)
            .order_by(Reading.datetime.desc())
            .first()
        )
        return row.datetime if row else None

    def list_readings(self, noise_site_id):
        return (
            Reading.query.filter_by(noise_site_id=noise_site_id)
            .order_by(Reading.datetime.asc())
            .all()
        )

    def upsert_readings(self, readings):
        # merge() keys off the (noise_site_id, datetime) primary key, so re-running
        # ingestion over an overlapping window updates existing rows instead of
        # raising an IntegrityError like the old app's plain append-only insert did.
        for reading in readings:
            db.session.merge(reading)
        db.session.commit()
        return len(readings)

    def aggregate_wind_rose(self, noise_site_id=None):
        # Set-based GROUP BY in the database - reading is a ~2.4M-row table,
        # far too large to pull into Python/pandas row-by-row the way the
        # smaller processed_reading-derived aggregates do. Sector bucketing
        # (floor((direction + 11.25) / 22.5) % 16) is portable SQLAlchemy
        # Core, not a raw SQL string, so it compiles correctly on both
        # SQLite (tests) and MySQL (prod).
        sector_index = (sa.func.floor((Reading.wind_direction + 11.25) / 22.5) % 16).label(
            "sector_index"
        )
        query = (
            db.session.query(
                Reading.noise_site_id,
                sector_index,
                sa.func.count(Reading.noise_site_id).label("sample_count"),
                sa.func.avg(Reading.wind_speed).label("avg_wind_speed"),
            )
            .filter(Reading.wind_direction.isnot(None))
            .filter(Reading.wind_speed.isnot(None))
            .filter(Reading.wind_speed < self.MAX_PLAUSIBLE_WIND_SPEED)
        )
        if noise_site_id:
            query = query.filter(Reading.noise_site_id.in_(noise_site_id))
        query = query.group_by(Reading.noise_site_id, sector_index)

        return [
            {
                "noise_site_id": row.noise_site_id,
                "direction_sector": DIRECTION_SECTORS[int(row.sector_index)],
                "sample_count": row.sample_count,
                "avg_wind_speed": float(row.avg_wind_speed),
            }
            for row in query.all()
        ]

    def aggregate_monthly_rainfall(self, noise_site_id=None):
        # Climatological - grouped by calendar month only (not year), so two
        # different years' Januaries combine into one month=1 row.
        month = sa.extract("month", Reading.datetime).label("month")
        query = (
            db.session.query(
                Reading.noise_site_id,
                month,
                sa.func.avg(Reading.rain_mm).label("avg_rain_mm"),
                sa.func.count(Reading.noise_site_id).label("sample_count"),
            )
            .filter(Reading.rain_mm.isnot(None))
            .filter(Reading.rain_mm < self.MAX_PLAUSIBLE_RAIN_MM)
        )
        if noise_site_id:
            query = query.filter(Reading.noise_site_id.in_(noise_site_id))
        query = query.group_by(Reading.noise_site_id, month)

        return [
            {
                "noise_site_id": row.noise_site_id,
                "month": int(row.month),
                "avg_rain_mm": float(row.avg_rain_mm),
                "sample_count": row.sample_count,
            }
            for row in query.all()
        ]
