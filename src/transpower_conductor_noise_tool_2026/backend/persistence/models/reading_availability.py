from transpower_conductor_noise_tool_2026.backend.extensions import db

# One row per noise_site_id - the true full-history min/max datetime and row
# count over processed_reading, unscoped by any Charts tab filter (site
# selection, date range, condition, conductor/grease, detection_logic,
# show_historical). See
# backend/persistence/repositories/processed_reading_repository.py::aggregate_availability
# for how these stats are computed and scripts/generate_reading_availability.py
# for how this table is (re)generated. Backs the Charts tab's "Data
# Availability Timeline", which is deliberately decoupled from every other
# Charts tab option - see chart_service.py::get_availability_timeline.


class ReadingAvailability(db.Model):
    __tablename__ = "reading_availability"

    noise_site_id = db.Column(db.Integer, primary_key=True)

    min_datetime = db.Column(db.DateTime, nullable=False)
    max_datetime = db.Column(db.DateTime, nullable=False)
    row_count = db.Column(db.Integer, nullable=False)
    computed_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
