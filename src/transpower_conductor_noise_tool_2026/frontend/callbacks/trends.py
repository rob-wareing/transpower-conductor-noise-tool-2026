from dash import Input, Output

from transpower_conductor_noise_tool_2026.shared.contracts import (
    AgeEffectsFilters,
    ConductorSummaryFilters,
    RainRateVsLevelFilters,
)

from ..client import BackendClient


def _is_hide_data_active(n_clicks):
    return bool(n_clicks) and n_clicks % 2 == 1


def _hide_marker_traces(figure):
    # Swap which trace represents each site in the legend, rather than just
    # hiding the marker trace outright (visible=False drops a trace from the
    # legend too, which would leave the legend empty). The marker and its fit
    # line share a legendgroup (see trends_service.py) - normally the marker
    # is the legend entry (showlegend defaults True) and the line is
    # suppressed (showlegend=False); with data hidden, that flips so the
    # legend shows each site by its line colour/style instead. A site with no
    # fit line (too few qualifying points) correctly drops out of the legend
    # entirely here - there's nothing left on the chart to label.
    for trace in figure.get("data", []):
        if trace.get("mode") == "markers":
            trace["visible"] = False
            trace["showlegend"] = False
        elif trace.get("mode") == "lines":
            trace["showlegend"] = True
    return figure


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("trends-rain-rate-site-select", "options"),
        Input("trends-rain-rate-init", "n_intervals"),
    )
    def populate_rain_rate_site_options(_n_intervals):
        if client is None:
            return []

        return [
            {"label": f"({site.noise_site_id}) {site.site_name}", "value": site.noise_site_id}
            for site in client.get_sites()
        ]

    @dash_app.callback(
        Output("trends-rain-rate-hide-data-button", "children"),
        Input("trends-rain-rate-hide-data-button", "n_clicks"),
    )
    def toggle_rain_rate_hide_data_label(n_clicks):
        return "Show data" if _is_hide_data_active(n_clicks) else "Hide data"

    @dash_app.callback(
        Output("trends-rain-rate-chart", "figure"),
        Input("trends-rain-rate-init", "n_intervals"),
        Input("trends-rain-rate-detection-logic", "value"),
        Input("trends-rain-rate-metric", "value"),
        Input("trends-rain-rate-site-select", "value"),
        Input("trends-rain-rate-include-dry", "value"),
        Input("trends-rain-rate-hide-data-button", "n_clicks"),
    )
    def refresh_rain_rate_chart(
        _n_intervals, detection_logic, metric, site_ids, include_dry, hide_data_n_clicks
    ):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure

        filters = RainRateVsLevelFilters(
            noise_site_id=site_ids or [],
            detection_logic=detection_logic or "original",
            metric=metric or "l90",
            include_dry=bool(include_dry),
        )
        figure = client.get_rain_rate_vs_level_chart(filters)
        if _is_hide_data_active(hide_data_n_clicks):
            figure = _hide_marker_traces(figure)
        return figure

    @dash_app.callback(
        Output("trends-conductor-summary-site-select", "options"),
        Input("trends-conductor-summary-init", "n_intervals"),
    )
    def populate_conductor_summary_site_options(_n_intervals):
        if client is None:
            return []

        return [
            {"label": f"({site.noise_site_id}) {site.site_name}", "value": site.noise_site_id}
            for site in client.get_sites()
        ]

    @dash_app.callback(
        Output("trends-conductor-summary-chart", "figure"),
        Input("trends-conductor-summary-init", "n_intervals"),
        Input("trends-conductor-summary-metric", "value"),
        Input("trends-conductor-summary-detection-logic", "value"),
        Input("trends-conductor-summary-duration", "value"),
        Input("trends-conductor-summary-site-select", "value"),
    )
    def refresh_conductor_summary_chart(
        _n_intervals, metric, detection_logic, measurement_duration_minutes, site_ids
    ):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure

        filters = ConductorSummaryFilters(
            noise_site_id=site_ids or [],
            metric=metric or "l90",
            detection_logic=detection_logic or "original",
            measurement_duration_minutes=measurement_duration_minutes or 15,
        )
        return client.get_conductor_summary_chart(filters)

    @dash_app.callback(
        Output("trends-age-effects-site-select", "options"),
        Input("trends-age-effects-init", "n_intervals"),
    )
    def populate_age_effects_site_options(_n_intervals):
        if client is None:
            return []

        return [
            {"label": f"({site.noise_site_id}) {site.site_name}", "value": site.noise_site_id}
            for site in client.get_sites()
        ]

    @dash_app.callback(
        Output("trends-age-effects-hide-data-button", "children"),
        Input("trends-age-effects-hide-data-button", "n_clicks"),
    )
    def toggle_age_effects_hide_data_label(n_clicks):
        return "Show data" if _is_hide_data_active(n_clicks) else "Hide data"

    @dash_app.callback(
        Output("trends-age-effects-chart", "figure"),
        Input("trends-age-effects-init", "n_intervals"),
        Input("trends-age-effects-detection-logic", "value"),
        Input("trends-age-effects-metric", "value"),
        Input("trends-age-effects-site-select", "value"),
        Input("trends-age-effects-hide-data-button", "n_clicks"),
    )
    def refresh_age_effects_chart(
        _n_intervals, detection_logic, metric, site_ids, hide_data_n_clicks
    ):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure

        filters = AgeEffectsFilters(
            noise_site_id=site_ids or [],
            detection_logic=detection_logic or "original",
            metric=metric or "l90",
        )
        figure = client.get_age_effects_chart(filters)
        if _is_hide_data_active(hide_data_n_clicks):
            figure = _hide_marker_traces(figure)
        return figure
