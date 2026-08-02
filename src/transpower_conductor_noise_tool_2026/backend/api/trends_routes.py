from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.backend.domain.trends_service import (
    get_conductor_summary,
    get_rain_rate_vs_level,
)
from transpower_conductor_noise_tool_2026.shared.contracts import (
    ConductorSummaryFilters,
    RainRateVsLevelFilters,
)

bp = Blueprint("trends", __name__, url_prefix="/api")


@bp.post("/trends/conductor-summary")
def conductor_summary():
    try:
        filters = ConductorSummaryFilters.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    return jsonify({"conductor_summary_chart": get_conductor_summary(filters)})


@bp.post("/trends/rain-rate-vs-level")
def rain_rate_vs_level():
    try:
        filters = RainRateVsLevelFilters.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    return jsonify({"rain_rate_vs_level_chart": get_rain_rate_vs_level(filters)})
