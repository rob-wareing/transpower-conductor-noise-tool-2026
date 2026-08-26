import plotly.graph_objects as go
from dash import Input, Output

from ..client import BackendClient
from .locations import _build_monthly_rainfall_figure, _build_wind_rose_figure, _empty_figure


def _year_month_param(year, month):
    if year is None or month is None:
        return None
    return f"{year:04d}-{month:02d}"


def _build_range_stats_figure(rows, field_prefix, title, y_title):
    if not rows:
        return _empty_figure(f"No data for {title.lower()} in this range")

    labels = [f"{row.year:04d}-{row.month:02d}" for row in rows]
    mins = [getattr(row, f"min_{field_prefix}") for row in rows]
    maxs = [getattr(row, f"max_{field_prefix}") for row in rows]
    avgs = [getattr(row, f"avg_{field_prefix}") for row in rows]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=labels, y=maxs, mode="lines", line=dict(width=0), showlegend=False)
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=mins,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(31, 119, 180, 0.2)",
            name="Min-Max range",
        )
    )
    figure.add_trace(
        go.Scatter(x=labels, y=avgs, mode="lines+markers", line=dict(width=2), name="Mean")
    )
    figure.update_layout(title=title, yaxis_title=y_title, height=400)
    return figure


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("weather-site-select", "options"),
        Input("weather-init", "n_intervals"),
    )
    def populate_weather_site_options(_n_intervals):
        if client is None:
            return []

        return [
            {"label": f"({site.noise_site_id}) {site.site_name}", "value": site.noise_site_id}
            for site in client.get_sites()
        ]

    @dash_app.callback(
        Output("weather-wind-rose", "figure"),
        Input("weather-site-select", "value"),
        Input("weather-start-month", "value"),
        Input("weather-start-year", "value"),
        Input("weather-end-month", "value"),
        Input("weather-end-year", "value"),
    )
    def update_weather_wind_rose(site_id, start_month, start_year, end_month, end_year):
        if site_id is None:
            return _empty_figure("Select a site to view its wind rose")
        if client is None:
            return _empty_figure("No wind data for this site")

        sectors = client.get_wind_rose(
            site_id,
            start=_year_month_param(start_year, start_month),
            end=_year_month_param(end_year, end_month),
        )
        if not sectors:
            return _empty_figure("No wind data for this site")
        return _build_wind_rose_figure(sectors)

    @dash_app.callback(
        Output("weather-monthly-rainfall", "figure"),
        Input("weather-site-select", "value"),
        Input("weather-start-month", "value"),
        Input("weather-start-year", "value"),
        Input("weather-end-month", "value"),
        Input("weather-end-year", "value"),
    )
    def update_weather_monthly_rainfall(site_id, start_month, start_year, end_month, end_year):
        if site_id is None:
            return _empty_figure("Select a site to view its monthly rainfall")
        if client is None:
            return _empty_figure("No rainfall data for this site")

        months = client.get_monthly_rainfall(
            site_id,
            start=_year_month_param(start_year, start_month),
            end=_year_month_param(end_year, end_month),
        )
        if not months:
            return _empty_figure("No rainfall data for this site")
        return _build_monthly_rainfall_figure(months)

    @dash_app.callback(
        Output("weather-rainfall-stats", "figure"),
        Output("weather-windspeed-stats", "figure"),
        Input("weather-site-select", "value"),
        Input("weather-start-month", "value"),
        Input("weather-start-year", "value"),
        Input("weather-end-month", "value"),
        Input("weather-end-year", "value"),
    )
    def update_weather_range_stats(site_id, start_month, start_year, end_month, end_year):
        placeholder = (
            _empty_figure("Select a site and date range to view monthly stats"),
            _empty_figure("Select a site and date range to view monthly stats"),
        )
        if site_id is None or client is None:
            return placeholder

        start = _year_month_param(start_year, start_month)
        end = _year_month_param(end_year, end_month)
        if start is None and end is None:
            return placeholder

        rows = client.get_monthly_weather_stats(site_id, start=start, end=end)
        return (
            _build_range_stats_figure(rows, "rain_mm", "Monthly Rainfall Range", "Rain (mm)"),
            _build_range_stats_figure(
                rows, "wind_speed", "Monthly Wind Speed Range", "Wind speed (m/s)"
            ),
        )
