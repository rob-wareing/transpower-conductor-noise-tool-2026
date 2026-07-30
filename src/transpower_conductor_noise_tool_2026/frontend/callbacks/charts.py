import flask
import pandas as pd
from dash import Input, Output, State, dcc, html, no_update
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters, ProcessedReadingUpdate

from ..client import BackendClient

EDITABLE_TABLE_FIELDS = ["is_wet", "include"]


def _conductor_options(events, site_ids, field):
    if site_ids:
        events = [event for event in events if event.noise_site_id in site_ids]
    values = sorted({getattr(event, field) for event in events if getattr(event, field)})
    return [{"label": value, "value": value} for value in values]


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
        Output("chart-conductor-treatment", "options"),
        Output("chart-conductor-treatment", "value"),
        Input("chart-site-select", "value"),
        State("chart-conductor-treatment", "value"),
    )
    def populate_conductor_treatment_options(site_ids, current_value):
        if client is None:
            return [], []
        events = client.get_reconductoring_events()
        options = _conductor_options(events, site_ids, "conductor_and_treatment")
        valid_values = {option["value"] for option in options}
        kept = [value for value in (current_value or []) if value in valid_values]
        return options, kept

    @dash_app.callback(
        Output("chart-grease", "options"),
        Output("chart-grease", "value"),
        Input("chart-site-select", "value"),
        State("chart-grease", "value"),
    )
    def populate_grease_options(site_ids, current_value):
        if client is None:
            return [], []
        events = client.get_reconductoring_events()
        options = _conductor_options(events, site_ids, "grease")
        valid_values = {option["value"] for option in options}
        kept = [value for value in (current_value or []) if value in valid_values]
        return options, kept

    @dash_app.callback(
        Output("noise-chart", "figure"),
        Output("timeline-chart", "figure"),
        Input("chart-init", "n_intervals"),
        Input("chart-site-select", "value"),
        Input("chart-date-range", "start_date"),
        Input("chart-date-range", "end_date"),
        Input("chart-condition", "value"),
        Input("chart-parameter", "value"),
        Input("chart-interval-weeks", "value"),
        Input("chart-conductor-treatment", "value"),
        Input("chart-grease", "value"),
        Input("chart-plot-by", "value"),
    )
    def refresh_charts(
        _n_intervals,
        site_ids,
        start_date,
        end_date,
        condition,
        parameter,
        interval_weeks,
        conductor_and_treatment,
        grease,
        plot_by,
    ):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure, empty_figure

        filters = ChartFilters(
            noise_site_id=site_ids or [],
            start_date=start_date,
            end_date=end_date,
            condition=condition or "all",
            parameter=parameter or "tone_100hz",
            interval_weeks=interval_weeks or 2,
            conductor_and_treatment=conductor_and_treatment or [],
            grease=grease or [],
            plot_by=plot_by or "datetime",
        )
        charts = client.get_charts(filters)
        return charts["noise_chart"], charts["timeline_chart"]

    @dash_app.callback(
        Output("chart-table-collapse", "is_open"),
        Input("chart-toggle-table-button", "n_clicks"),
        State("chart-table-collapse", "is_open"),
    )
    def toggle_chart_table(n_clicks, is_open):
        if not n_clicks:
            return False
        return not is_open

    @dash_app.callback(
        Output("chart-table", "data"),
        Input("chart-init", "n_intervals"),
        Input("chart-site-select", "value"),
        Input("chart-date-range", "start_date"),
        Input("chart-date-range", "end_date"),
        Input("chart-condition", "value"),
        Input("chart-conductor-treatment", "value"),
        Input("chart-grease", "value"),
        Input("chart-table-status", "children"),
    )
    def refresh_chart_table(
        _n_intervals, site_ids, start_date, end_date, condition, conductor_and_treatment, grease, _status
    ):
        if client is None:
            return []

        filters = ChartFilters(
            noise_site_id=site_ids or [],
            start_date=start_date,
            end_date=end_date,
            condition=condition or "all",
            conductor_and_treatment=conductor_and_treatment or [],
            grease=grease or [],
        )
        return [row.model_dump(mode="json") for row in client.get_chart_table_rows(filters)]

    @dash_app.callback(
        Output("chart-table-status", "children"),
        Input("chart-table-save-button", "n_clicks"),
        State("chart-table", "data"),
        prevent_initial_call=True,
    )
    def save_chart_table(n_clicks, rows):
        if not n_clicks or client is None:
            return ""

        cookies = flask.request.cookies
        errors = []

        for row in rows:
            fields = {field: row.get(field) for field in EDITABLE_TABLE_FIELDS}
            try:
                update = ProcessedReadingUpdate(**fields)
            except ValidationError as exc:
                errors.append(f"reading {row['id']}: {exc.errors()[0]['msg']}")
                continue

            response = client.update_processed_reading(row["id"], update, cookies=cookies)
            if response.status_code != 200:
                errors.append(f"reading {row['id']}: {response.json().get('error')}")

        if errors:
            return html.Ul([html.Li(error) for error in errors])
        return "Saved."

    @dash_app.callback(
        Output("chart-download-table", "data"),
        Input("chart-export-table-button", "n_clicks"),
        State("chart-table", "data"),
        prevent_initial_call=True,
    )
    def export_chart_table(n_clicks, rows):
        if not n_clicks or not rows:
            return no_update
        return dcc.send_data_frame(pd.DataFrame(rows).to_csv, "events.csv", index=False)

    @dash_app.callback(
        Output("chart-download-plot", "data"),
        Input("chart-export-plot-button", "n_clicks"),
        State("noise-chart", "figure"),
        prevent_initial_call=True,
    )
    def export_chart_plot(n_clicks, figure):
        if not n_clicks or not figure or not figure.get("data"):
            return no_update

        records = [
            {"series": trace.get("name", ""), "x": x, "y": y}
            for trace in figure["data"]
            for x, y in zip(trace.get("x", []), trace.get("y", []))
        ]
        if not records:
            return no_update
        return dcc.send_data_frame(pd.DataFrame(records).to_csv, "processed.csv", index=False)
