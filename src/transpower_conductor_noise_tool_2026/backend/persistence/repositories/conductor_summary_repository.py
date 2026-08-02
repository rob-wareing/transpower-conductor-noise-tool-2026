import sqlalchemy as sa

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.conductor_summary import (
    ConductorSummary,
)


class ConductorSummaryRepository:
    def list_summaries(self):
        return ConductorSummary.query.order_by(
            ConductorSummary.noise_site_id.asc(), ConductorSummary.detection_logic.asc()
        ).all()

    def replace_all(self, records):
        # The whole table is always fully regenerated, not incrementally
        # patched - at most ~2 rows per site, so a plain delete-then-insert in
        # one transaction is cheap and avoids reconciling stale rows for a
        # site/detection_logic combination that no longer has any matching
        # processed_reading data.
        table = ConductorSummary.__table__
        db.session.execute(sa.delete(table))
        if records:
            db.session.execute(sa.insert(table), records)
        db.session.commit()
        return len(records)
