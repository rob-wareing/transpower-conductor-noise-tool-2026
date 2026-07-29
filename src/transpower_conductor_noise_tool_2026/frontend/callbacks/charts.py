from dash import Input, Output

from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters

from ..client import BackendClient


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("chart-site-select", "options"),
        Input("chart-init", "n_intervals"),
    )
    def populate_site_options(_n_intervals):
        if client is None:
            return []

        return [
            {"label": f"({site.noise_site_id}) {site.site_name}", "value": site.noise_site_id}
            for site in client.get_sites()
        ]

    @dash_app.callback(
        Output("noise-chart", "figure"),
        Output("timeline-chart", "figure"),
        Input("chart-init", "n_intervals"),
        Input("chart-site-select", "value"),
        Input("chart-date-range", "start_date"),
        Input("chart-date-range", "end_date"),
        Input("chart-condition", "value"),
        Input("chart-parameter", "value"),
    )
    def refresh_charts(_n_intervals, site_ids, start_date, end_date, condition, parameter):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure, empty_figure

        filters = ChartFilters(
            noise_site_id=site_ids or [],
            start_date=start_date,
            end_date=end_date,
            condition=condition or "all",
            parameter=parameter or "tone_100hz",
        )
        charts = client.get_charts(filters)
        return charts["noise_chart"], charts["timeline_chart"]
