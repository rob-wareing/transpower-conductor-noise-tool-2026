from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.backend.api.auth_guard import require_write_access
from transpower_conductor_noise_tool_2026.backend.domain.reconductoring_service import (
    create_reconductoring_event,
    delete_reconductoring_event,
    list_reconductoring_events,
    update_reconductoring_event,
)
from transpower_conductor_noise_tool_2026.shared.contracts import (
    ReconductoringCreate,
    ReconductoringDetail,
    ReconductoringUpdate,
)

bp = Blueprint("reconductoring", __name__, url_prefix="/api/reconductoring")


@bp.get("")
def reconductoring():
    items = [event.model_dump(mode="json") for event in list_reconductoring_events()]
    return jsonify({"items": items, "count": len(items)})


@bp.post("")
@require_write_access
def create():
    try:
        data = ReconductoringCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    event = create_reconductoring_event(data)
    return (
        jsonify({"event": ReconductoringDetail.model_validate(event).model_dump(mode="json")}),
        201,
    )


@bp.patch("/<int:event_id>")
@require_write_access
def update(event_id):
    try:
        update_data = ReconductoringUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    event = update_reconductoring_event(event_id, update_data)
    if event is None:
        return jsonify({"error": "reconductoring event not found"}), 404

    return jsonify({"event": ReconductoringDetail.model_validate(event).model_dump(mode="json")})


@bp.delete("/<int:event_id>")
@require_write_access
def delete(event_id):
    if not delete_reconductoring_event(event_id):
        return jsonify({"error": "reconductoring event not found"}), 404
    return jsonify({"status": "ok"})
