import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.rain_rate_fit import (
    RainRateFit,
)


class RainRateFitRepository:
    def list_fits(self, noise_site_id=None, detection_logic=None, metric=None):
        query = RainRateFit.query
        if noise_site_id:
            query = query.filter(RainRateFit.noise_site_id.in_(noise_site_id))
        if detection_logic is not None:
            query = query.filter(RainRateFit.detection_logic == detection_logic)
        if metric is not None:
            query = query.filter(RainRateFit.metric == metric)
        return query.order_by(RainRateFit.noise_site_id.asc()).all()

    def replace_all(self, records):
        # The whole table is always fully regenerated, not incrementally
        # patched - a plain delete-then-insert in one transaction is cheap
        # and avoids reconciling stale rows for a site/detection_logic/metric
        # combination that no longer has enough matching processed_reading
        # data to fit.
        table = RainRateFit.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
