from flask import Blueprint, jsonify

from transpower_conductor_noise_tool_2026.backend.domain.site_climate_service import (
    get_monthly_rainfall,
    get_wind_rose,
)
from transpower_conductor_noise_tool_2026.shared.contracts import MonthlyRainfall, WindRoseSector

bp = Blueprint("site_climate", __name__, url_prefix="/api")


@bp.get("/sites/<int:noise_site_id>/wind-rose")
def wind_rose(noise_site_id):
    items = [
        WindRoseSector.model_validate(row).model_dump() for row in get_wind_rose(noise_site_id)
    ]
    return jsonify({"items": items, "count": len(items)})


@bp.get("/sites/<int:noise_site_id>/monthly-rainfall")
def monthly_rainfall(noise_site_id):
    items = [
        MonthlyRainfall.model_validate(row).model_dump()
        for row in get_monthly_rainfall(noise_site_id)
    ]
    return jsonify({"items": items, "count": len(items)})
