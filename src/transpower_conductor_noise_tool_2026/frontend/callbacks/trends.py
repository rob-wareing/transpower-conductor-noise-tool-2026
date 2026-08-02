from dash import Input, Output

from transpower_conductor_noise_tool_2026.shared.contracts import ConductorSummaryFilters

from ..client import BackendClient


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("trends-conductor-summary-chart", "figure"),
        Input("trends-conductor-summary-init", "n_intervals"),
        Input("trends-conductor-summary-detection-logic", "value"),
        Input("trends-conductor-summary-duration", "value"),
    )
    def refresh_conductor_summary_chart(
        _n_intervals, detection_logic, measurement_duration_minutes
    ):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure

        filters = ConductorSummaryFilters(
            detection_logic=detection_logic or "original",
            measurement_duration_minutes=measurement_duration_minutes or 15,
        )
        return client.get_conductor_summary_chart(filters)
