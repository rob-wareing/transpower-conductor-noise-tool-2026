from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from transpower_conductor_noise_tool_2026.backend.api.auth_guard import require_write_access
from transpower_conductor_noise_tool_2026.backend.domain.historical_service import (
    create_historical_result,
    delete_historical_result,
    list_historical_results,
    update_historical_result,
)
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.shared.contracts import (
    HistoricalResultCreate,
    HistoricalResultDetail,
    HistoricalResultUpdate,
)

bp = Blueprint("historical", __name__, url_prefix="/api/historical")


@bp.get("")
def historical():
    items = [result.model_dump(mode="json") for result in list_historical_results()]
    return jsonify({"items": items, "count": len(items)})


@bp.post("")
@require_write_access
def create():
    try:
        data = HistoricalResultCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    try:
        result = create_historical_result(data)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "unknown site"}), 400

    return (
        jsonify({"result": HistoricalResultDetail.model_validate(result).model_dump(mode="json")}),
        201,
    )


@bp.patch("/<int:result_id>")
@require_write_access
def update(result_id):
    try:
        update_data = HistoricalResultUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    result = update_historical_result(result_id, update_data)
    if result is None:
        return jsonify({"error": "historical result not found"}), 404

    return jsonify({"result": HistoricalResultDetail.model_validate(result).model_dump(mode="json")})


@bp.delete("/<int:result_id>")
@require_write_access
def delete(result_id):
    if not delete_historical_result(result_id):
        return jsonify({"error": "historical result not found"}), 404
    return jsonify({"status": "ok"})
