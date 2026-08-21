import dash
import flask
import pandas as pd
from dash import Input, Output, State, dcc, html, no_update
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters, ProcessedReadingUpdate

from ..client import BackendClient

EDITABLE_TABLE_FIELDS = ["is_wet", "include"]
MEASUREMENT_DURATION_TO_MINUTES = {"1min": 1, "15min": 15}


def _conductor_options(events, site_ids, field):
    # events: dicts from the chart-reconductoring-events-store dcc.Store
    # (JSON-serialized, so dict access rather than attribute access).
    if site_ids:
        events = [event for event in events if event["noise_site_id"] in site_ids]
    values = sorted({event[field] for event in events if event.get(field)})
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
        Output("chart-site-select", "value"),
        Input("chart-select-all-sites-button", "n_clicks"),
        Input("chart-clear-sites-button", "n_clicks"),
        State("chart-site-select", "options"),
        prevent_initial_call=True,
    )
    def bulk_select_sites(_select_all_clicks, _clear_clicks, options):
        # One click selects every currently-listed site (or clears the
        # selection) instead of clicking each site in the dropdown
        # individually. Only fires on an actual button click
        # (prevent_initial_call=True) - manual per-site selection in the
        # dropdown itself is untouched by this callback.
        if dash.ctx.triggered_id == "chart-select-all-sites-button":
            return [option["value"] for option in options or []]
        return []

    @dash_app.callback(
        Output("chart-reconductoring-events-store", "data"),
        Input("chart-init", "n_intervals"),
    )
    def populate_reconductoring_events_store(_n_intervals):
        # Fetched once per page load and shared by both dropdowns below,
        # instead of each independently calling client.get_reconductoring_events()
        # (previously two identical HTTP round trips on every default load).
        if client is None:
            return []
        return [event.model_dump(mode="json") for event in client.get_reconductoring_events()]

    @dash_app.callback(
        Output("chart-conductor-treatment", "options"),
        Output("chart-conductor-treatment", "value"),
        Input("chart-site-select", "value"),
        Input("chart-reconductoring-events-store", "data"),
        State("chart-conductor-treatment", "value"),
    )
    def populate_conductor_treatment_options(site_ids, events, current_value):
        events = events or []
        options = _conductor_options(events, site_ids, "conductor_and_treatment")
        valid_values = {option["value"] for option in options}
        kept = [value for value in (current_value or []) if value in valid_values]
        return options, kept

    @dash_app.callback(
        Output("chart-grease", "options"),
        Output("chart-grease", "value"),
        Input("chart-site-select", "value"),
        Input("chart-reconductoring-events-store", "data"),
        State("chart-grease", "value"),
    )
    def populate_grease_options(site_ids, events, current_value):
        events = events or []
        if client is None:
            return [], []
        options = _conductor_options(events, site_ids, "grease")
        descriptions = {item.grease: item.description for item in client.get_grease_descriptions()}
        for option in options:
            description = descriptions.get(option["value"])
            if description:
                option["label"] = f"{option['value']} - {description}"
        valid_values = {option["value"] for option in options}
        kept = [value for value in (current_value or []) if value in valid_values]
        return options, kept

    @dash_app.callback(
        Output("noise-chart", "figure"),
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
        Input("chart-measurement-duration", "value"),
        Input("chart-detection-logic", "value"),
        Input("chart-show-historical", "value"),
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
        measurement_duration,
        detection_logic,
        show_historical,
    ):
        empty_figure = {"data": [], "layout": {}}
        if client is None:
            return empty_figure

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
            measurement_duration=MEASUREMENT_DURATION_TO_MINUTES.get(measurement_duration, 15),
            detection_logic=detection_logic or "original",
            show_historical=bool(show_historical),
        )
        charts = client.get_charts(filters)
        return charts["noise_chart"]

    @dash_app.callback(
        Output("timeline-chart", "figure"),
        Input("chart-init", "n_intervals"),
    )
    def refresh_chart_timeline(_n_intervals):
        # Deliberately the ONLY Input - the Data Availability Timeline must
        # not change based on any Charts tab filter (site, date, condition,
        # conductor/grease, detection_logic, show_historical). See
        # chart_service.get_availability_timeline.
        if client is None:
            return {"data": [], "layout": {}}
        return client.get_chart_timeline()

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
        Input("chart-measurement-duration", "value"),
        Input("chart-detection-logic", "value"),
        Input("chart-table-collapse", "is_open"),
    )
    def refresh_chart_table(
        _n_intervals,
        site_ids,
        start_date,
        end_date,
        condition,
        conductor_and_treatment,
        grease,
        _status,
        measurement_duration,
        detection_logic,
        is_open,
    ):
        # The table is collapsed by default - skip the fetch entirely until
        # the user actually opens it, instead of duplicating the figures
        # endpoint's full fetch/pipeline on every page load regardless.
        if not is_open:
            return no_update
        if client is None:
            return []

        filters = ChartFilters(
            noise_site_id=site_ids or [],
            start_date=start_date,
            end_date=end_date,
            condition=condition or "all",
            conductor_and_treatment=conductor_and_treatment or [],
            grease=grease or [],
            measurement_duration=MEASUREMENT_DURATION_TO_MINUTES.get(measurement_duration, 15),
            detection_logic=detection_logic or "original",
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
