import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db


class Reconductoring(db.Model):
    __tablename__ = "reconductoring"

    # The old repo used a composite (noise_site_id, conductor) primary key here,
    # even though `conductor` is never set by its own UI (left blank) - a second
    # reconductoring event for the same site with a blank `conductor` collides on
    # that key. `id` was already used everywhere else in that app as the row's
    # effective identity (add/delete diffing), so it's the real primary key here.
    id = db.Column(db.Integer, primary_key=True)
    noise_site_id = db.Column(db.Integer, nullable=False)
    conductor = db.Column(db.String(200), nullable=True)
    grease = db.Column(db.String(50), nullable=True)
    conductor_and_treatment = db.Column(db.String(200), nullable=True)
    reconductoring_date = db.Column(db.Date, nullable=False)
    plot_linestyle = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.String(200), nullable=True)
    # Whether this event should anchor ReconductoringRepository.latest_by_site()
    # (and therefore processed_reading.reconductoring_age) - not every logged
    # row is a genuine new-conductor event, some are just a grease/treatment
    # change on the same physical conductor. Defaults True (unlike
    # site.is_ignored's False default) so adding this column changes nothing
    # until a specific row is deliberately flagged as not a real reconductoring.
    for_reconductoring_age = db.Column(
        db.Boolean, nullable=False, default=True, server_default=sa.true()
    )

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["noise_site_id"], ["site.noise_site_id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
    )
