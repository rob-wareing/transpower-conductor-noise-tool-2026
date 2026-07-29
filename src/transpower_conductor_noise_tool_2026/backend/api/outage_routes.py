from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from transpower_conductor_noise_tool_2026.backend.api.auth_guard import require_write_access
from transpower_conductor_noise_tool_2026.backend.domain.outage_service import (
    create_outage,
    delete_outage,
    list_outage_types,
    list_outages,
    update_outage,
)
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.shared.contracts import (
    OutageCreate,
    OutageDetail,
    OutageUpdate,
)

bp = Blueprint("outages", __name__, url_prefix="/api/outages")


@bp.get("")
def outages():
    items = [outage.model_dump(mode="json") for outage in list_outages()]
    return jsonify({"items": items, "count": len(items)})


@bp.get("/types")
def outage_types():
    return jsonify({"items": list_outage_types()})


@bp.post("")
@require_write_access
def create():
    try:
        data = OutageCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    try:
        outage = create_outage(data)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": f"unknown outage_type '{data.outage_type}' or site"}), 400

    return jsonify({"outage": OutageDetail.model_validate(outage).model_dump(mode="json")}), 201


@bp.patch("/<int:outage_id>")
@require_write_access
def update(outage_id):
    try:
        update_data = OutageUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    try:
        outage = update_outage(outage_id, update_data)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "unknown outage_type"}), 400

    if outage is None:
        return jsonify({"error": "outage not found"}), 404

    return jsonify({"outage": OutageDetail.model_validate(outage).model_dump(mode="json")})


@bp.delete("/<int:outage_id>")
@require_write_access
def delete(outage_id):
    if not delete_outage(outage_id):
        return jsonify({"error": "outage not found"}), 404
    return jsonify({"status": "ok"})
