import flask
import pandas as pd
from dash import Input, Output, State, dcc, html, no_update
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import (
    ReconductoringCreate,
    ReconductoringUpdate,
)

from ..client import BackendClient

EDITABLE_FIELDS = ["noise_site_id", "conductor_and_treatment", "grease", "reconductoring_date", "notes"]


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("reconductoring-table", "data"),
        Input("reconductoring-init", "n_intervals"),
        Input("reconductoring-status", "children"),
    )
    def refresh_reconductoring_table(_n_intervals, _status):
        if client is None:
            return []
        return [event.model_dump(mode="json") for event in client.get_reconductoring_events()]

    @dash_app.callback(
        Output("reconductoring-table", "data", allow_duplicate=True),
        Input("reconductoring-add-row-button", "n_clicks"),
        State("reconductoring-table", "data"),
        prevent_initial_call=True,
    )
    def add_row(n_clicks, rows):
        if not n_clicks:
            return rows
        return rows + [{field: "" for field in EDITABLE_FIELDS}]

    @dash_app.callback(
        Output("reconductoring-status", "children"),
        Input("reconductoring-save-button", "n_clicks"),
        State("reconductoring-table", "data"),
        prevent_initial_call=True,
    )
    def save_reconductoring(n_clicks, rows):
        if not n_clicks or client is None:
            return ""

        cookies = flask.request.cookies
        server_events = {event.id: event for event in client.get_reconductoring_events()}
        submitted_ids = {row["id"] for row in rows if row.get("id")}

        errors = []

        for event_id in server_events.keys() - submitted_ids:
            response = client.delete_reconductoring_event(event_id, cookies=cookies)
            if response.status_code != 200:
                errors.append(f"delete event {event_id}: {response.json().get('error')}")

        for row in rows:
            fields = {field: row.get(field) or None for field in EDITABLE_FIELDS}

            if row.get("id"):
                try:
                    update = ReconductoringUpdate(**fields)
                except ValidationError as exc:
                    errors.append(f"event {row['id']}: {exc.errors()[0]['msg']}")
                    continue
                response = client.update_reconductoring_event(row["id"], update, cookies=cookies)
                if response.status_code != 200:
                    errors.append(f"event {row['id']}: {response.json().get('error')}")
                continue

            if not any(fields.values()):
                continue  # blank unsaved new row - silently skipped, matches old app

            try:
                data = ReconductoringCreate(**fields)
            except ValidationError as exc:
                errors.append(f"new event: {exc.errors()[0]['msg']}")
                continue
            response = client.create_reconductoring_event(data, cookies=cookies)
            if response.status_code != 201:
                errors.append(f"new event: {response.json().get('error')}")

        if errors:
            return html.Ul([html.Li(error) for error in errors])
        return "Saved."

    @dash_app.callback(
        Output("reconductoring-download", "data"),
        Input("reconductoring-export-button", "n_clicks"),
        State("reconductoring-table", "data"),
        prevent_initial_call=True,
    )
    def export_reconductoring(n_clicks, rows):
        if not n_clicks or not rows:
            return no_update
        return dcc.send_data_frame(pd.DataFrame(rows).to_csv, "reconductoring.csv", index=False)
