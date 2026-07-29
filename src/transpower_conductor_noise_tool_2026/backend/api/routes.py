from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.backend.api.auth_guard import require_write_access
from transpower_conductor_noise_tool_2026.backend.domain.site_service import (
    list_site_details,
    list_site_summaries,
    update_site_fields,
)
from transpower_conductor_noise_tool_2026.shared.contracts import SiteDetail, SiteUpdate

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "backend-api"})


@bp.get("/sites")
def sites():
    items = [site.model_dump() for site in list_site_summaries()]
    return jsonify({"items": items, "count": len(items)})


@bp.get("/sites/detail")
def sites_detail():
    items = [site.model_dump() for site in list_site_details()]
    return jsonify({"items": items, "count": len(items)})


@bp.patch("/sites/<int:noise_site_id>")
@require_write_access
def update_site(noise_site_id):
    try:
        update = SiteUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        # exc.errors() includes a raw exception object in "ctx" for custom
        # validators, which isn't JSON-serializable - strip it.
        return jsonify({"error": exc.errors(include_context=False)}), 400

    site = update_site_fields(noise_site_id, update)
    if site is None:
        return jsonify({"error": "site not found"}), 404

    return jsonify({"site": SiteDetail.model_validate(site).model_dump()})
