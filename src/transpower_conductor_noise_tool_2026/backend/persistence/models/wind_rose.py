from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per (noise_site_id, direction_sector) - see
# backend/persistence/repositories/reading_repository.py::aggregate_wind_rose
# for how these stats are computed and scripts/generate_wind_rose.py for how
# this table is (re)generated from the raw reading table. A sector only
# exists once at least one matching reading row does - a site with wind data
# in only 9 of 16 sectors gets 9 rows, not 16 with some zeroed out.


class WindRose(db.Model):
    __tablename__ = "wind_rose"

    noise_site_id = db.Column(db.Integer, primary_key=True)
    direction_sector = db.Column(db.String(3), primary_key=True)

    sample_count = db.Column(db.Integer, nullable=False)
    avg_wind_speed = db.Column(db.Numeric(4, 1), nullable=False)
    computed_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
