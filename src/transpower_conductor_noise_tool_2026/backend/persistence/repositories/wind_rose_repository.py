import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.wind_rose import WindRose


class WindRoseRepository:
    def list_sectors(self, noise_site_id=None):
        query = WindRose.query
        if noise_site_id:
            query = query.filter(WindRose.noise_site_id.in_(noise_site_id))
        return query.order_by(WindRose.noise_site_id.asc(), WindRose.direction_sector.asc()).all()

    def replace_all(self, records):
        # The whole table is always fully regenerated, not incrementally
        # patched - at most 16 rows per site, so a plain delete-then-insert
        # in one transaction is cheap and avoids reconciling stale rows for
        # a sector that no longer has any matching reading data.
        table = WindRose.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
