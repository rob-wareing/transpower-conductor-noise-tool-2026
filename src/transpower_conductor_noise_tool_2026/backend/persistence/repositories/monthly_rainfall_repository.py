import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_rainfall import (
    MonthlyRainfall,
)


class MonthlyRainfallRepository:
    def list_months(self, noise_site_id=None, start_year_month=None, end_year_month=None):
        query = MonthlyRainfall.query
        if noise_site_id:
            query = query.filter(MonthlyRainfall.noise_site_id.in_(noise_site_id))
        if start_year_month is not None or end_year_month is not None:
            # Packed YYYYMM int (year * 100 + month) so a range comparison is
            # a single expression rather than a composite (year, month) tuple
            # comparison, which SQLite doesn't support.
            year_month = MonthlyRainfall.year * 100 + MonthlyRainfall.month
            if start_year_month is not None:
                query = query.filter(year_month >= start_year_month)
            if end_year_month is not None:
                query = query.filter(year_month <= end_year_month)
        return query.order_by(
            MonthlyRainfall.noise_site_id.asc(),
            MonthlyRainfall.year.asc(),
            MonthlyRainfall.month.asc(),
        ).all()

    def replace_all(self, records):
        # The whole table is always fully regenerated, not incrementally
        # patched - a modest row count per site (12 months x however many
        # years of history), so a plain delete-then-insert in one
        # transaction is cheap and avoids reconciling stale rows for a
        # month that no longer has any matching reading data.
        table = MonthlyRainfall.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
