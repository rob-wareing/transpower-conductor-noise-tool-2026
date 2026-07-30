from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.backend.api.auth_guard import require_write_access
from transpower_conductor_noise_tool_2026.backend.domain.processed_reading_service import (
    update_processed_reading,
)
from transpower_conductor_noise_tool_2026.shared.contracts import ProcessedReadingUpdate

bp = Blueprint("processed_readings", __name__, url_prefix="/api/processed-readings")


@bp.patch("/<int:reading_id>")
@require_write_access
def update(reading_id):
    try:
        update_data = ProcessedReadingUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    reading = update_processed_reading(reading_id, update_data)
    if reading is None:
        return jsonify({"error": "processed reading not found"}), 404

    return jsonify({"status": "ok"})
