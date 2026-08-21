from dash import Input, Output

from ..client import BackendClient
from .locations import _build_monthly_rainfall_figure, _build_wind_rose_figure, _empty_figure


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
    )
    def update_weather_wind_rose(site_id):
        if site_id is None:
            return _empty_figure("Select a site to view its wind rose")
        if client is None:
            return _empty_figure("No wind data for this site")

        sectors = client.get_wind_rose(site_id)
        if not sectors:
            return _empty_figure("No wind data for this site")
        return _build_wind_rose_figure(sectors)

    @dash_app.callback(
        Output("weather-monthly-rainfall", "figure"),
        Input("weather-site-select", "value"),
    )
    def update_weather_monthly_rainfall(site_id):
        if site_id is None:
            return _empty_figure("Select a site to view its monthly rainfall")
        if client is None:
            return _empty_figure("No rainfall data for this site")

        months = client.get_monthly_rainfall(site_id)
        if not months:
            return _empty_figure("No rainfall data for this site")
        return _build_monthly_rainfall_figure(months)
