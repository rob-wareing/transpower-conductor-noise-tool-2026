import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.monthly_weather_stats import (
    MonthlyWeatherStats,
)


class MonthlyWeatherStatsRepository:
    def list_months(self, noise_site_id=None, start_year_month=None, end_year_month=None):
        query = MonthlyWeatherStats.query
        if noise_site_id:
            query = query.filter(MonthlyWeatherStats.noise_site_id.in_(noise_site_id))
        if start_year_month is not None or end_year_month is not None:
            # Packed YYYYMM int (year * 100 + month) so a range comparison is
            # a single expression rather than a composite (year, month) tuple
            # comparison, which SQLite doesn't support.
            year_month = MonthlyWeatherStats.year * 100 + MonthlyWeatherStats.month
            if start_year_month is not None:
                query = query.filter(year_month >= start_year_month)
            if end_year_month is not None:
                query = query.filter(year_month <= end_year_month)
        return query.order_by(
            MonthlyWeatherStats.noise_site_id.asc(),
            MonthlyWeatherStats.year.asc(),
            MonthlyWeatherStats.month.asc(),
        ).all()

    def replace_all(self, records):
        # The whole table is always fully regenerated, not incrementally
        # patched - a modest row count per site (one row per month of
        # history), so a plain delete-then-insert in one transaction is
        # cheap and avoids reconciling stale rows for a month that no
        # longer has any matching reading data.
        table = MonthlyWeatherStats.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
