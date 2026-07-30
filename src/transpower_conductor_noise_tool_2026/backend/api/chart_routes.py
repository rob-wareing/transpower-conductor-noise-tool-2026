from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.backend.domain.chart_service import (
    get_chart_figures,
    get_chart_table_rows,
)
from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters, ChartTableRow

bp = Blueprint("charts", __name__, url_prefix="/api")


@bp.post("/charts")
def charts():
    try:
        filters = ChartFilters.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    noise_chart, timeline_chart = get_chart_figures(filters)
    return jsonify({"noise_chart": noise_chart, "timeline_chart": timeline_chart})


@bp.post("/charts/table")
def charts_table():
    try:
        filters = ChartFilters.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors(include_context=False)}), 400

    rows = get_chart_table_rows(filters)
    items = [ChartTableRow.model_validate(row).model_dump(mode="json") for row in rows]
    return jsonify({"items": items})
