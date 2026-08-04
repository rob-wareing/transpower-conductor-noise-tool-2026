import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_rainfall import (
    MonthlyRainfall,
)


class MonthlyRainfallRepository:
    def list_months(self, noise_site_id=None):
        query = MonthlyRainfall.query
        if noise_site_id:
            query = query.filter(MonthlyRainfall.noise_site_id.in_(noise_site_id))
        return query.order_by(MonthlyRainfall.noise_site_id.asc(), MonthlyRainfall.month.asc()).all()

    def replace_all(self, records):
        # The whole table is always fully regenerated, not incrementally
        # patched - at most 12 rows per site, so a plain delete-then-insert
        # in one transaction is cheap and avoids reconciling stale rows for
        # a month that no longer has any matching reading data.
        table = MonthlyRainfall.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
