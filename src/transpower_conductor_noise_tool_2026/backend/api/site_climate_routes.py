from flask import Blueprint, jsonify, request

from transpower_conductor_noise_tool_2026.backend.domain.site_climate_service import (
    get_monthly_rainfall,
    get_monthly_weather_stats,
    get_site_summary,
    get_wind_rose,
)
from transpower_conductor_noise_tool_2026.shared.contracts import (
    MonthlyRainfall,
    MonthlyWeatherStats,
    SiteActivitySummary,
    WindRoseSector,
)

bp = Blueprint("site_climate", __name__, url_prefix="/api")


def _parse_year_month(value):
    # "YYYY-MM" query param -> (year, month) tuple, or None if absent/
    # malformed - this is a frontend-controlled internal API (the month/year
    # dropdowns on the Weather tab only ever emit well-formed values), so a
    # bad value is treated as "no bound" rather than a 400.
    if not value:
        return None
    try:
        year_str, month_str = value.split("-", 1)
        return int(year_str), int(month_str)
    except ValueError:
        return None


def _date_range_args():
    return _parse_year_month(request.args.get("start")), _parse_year_month(request.args.get("end"))


@bp.get("/sites/<int:noise_site_id>/wind-rose")
def wind_rose(noise_site_id):
    start, end = _date_range_args()
    items = [
        WindRoseSector.model_validate(row).model_dump()
        for row in get_wind_rose(noise_site_id, start=start, end=end)
    ]
    return jsonify({"items": items, "count": len(items)})


@bp.get("/sites/<int:noise_site_id>/monthly-rainfall")
def monthly_rainfall(noise_site_id):
    start, end = _date_range_args()
    items = [
        MonthlyRainfall.model_validate(row).model_dump()
        for row in get_monthly_rainfall(noise_site_id, start=start, end=end)
    ]
    return jsonify({"items": items, "count": len(items)})


@bp.get("/sites/<int:noise_site_id>/monthly-weather-stats")
def monthly_weather_stats(noise_site_id):
    start, end = _date_range_args()
    items = [
        MonthlyWeatherStats.model_validate(row).model_dump()
        for row in get_monthly_weather_stats(noise_site_id, start=start, end=end)
    ]
    return jsonify({"items": items, "count": len(items)})


@bp.get("/sites/<int:noise_site_id>/summary")
def site_summary(noise_site_id):
    summary = SiteActivitySummary.model_validate(get_site_summary(noise_site_id))
    return jsonify(summary.model_dump(mode="json"))
