from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.historical_result import (
    HistoricalResult,
)


class HistoricalResultRepository:
    def list_results(self):
        return HistoricalResult.query.order_by(HistoricalResult.period_end_date.desc()).all()

    def find_by_id(self, result_id):
        return db.session.get(HistoricalResult, result_id)

    def add(self, result):
        db.session.add(result)
        db.session.commit()
        return result

    def save(self, result):
        db.session.commit()
        return result

    def delete(self, result):
        db.session.delete(result)
        db.session.commit()
