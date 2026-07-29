import flask
from dash import Input, Output, State, html
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import (
    HistoricalResultCreate,
    HistoricalResultUpdate,
)

from ..client import BackendClient

EDITABLE_FIELDS = ["noise_site_id", "period_end_date", "leq_adj", "tone_100hz"]


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("historical-table", "data"),
        Input("historical-init", "n_intervals"),
        Input("historical-status", "children"),
    )
    def refresh_historical_table(_n_intervals, _status):
        if client is None:
            return []
        return [result.model_dump(mode="json") for result in client.get_historical_results()]

    @dash_app.callback(
        Output("historical-table", "data", allow_duplicate=True),
        Input("historical-add-row-button", "n_clicks"),
        State("historical-table", "data"),
        prevent_initial_call=True,
    )
    def add_row(n_clicks, rows):
        if not n_clicks:
            return rows
        return rows + [{field: "" for field in EDITABLE_FIELDS}]

    @dash_app.callback(
        Output("historical-status", "children"),
        Input("historical-save-button", "n_clicks"),
        State("historical-table", "data"),
        prevent_initial_call=True,
    )
    def save_historical(n_clicks, rows):
        if not n_clicks or client is None:
            return ""

        cookies = flask.request.cookies
        server_results = {result.id: result for result in client.get_historical_results()}
        submitted_ids = {row["id"] for row in rows if row.get("id")}

        errors = []

        for result_id in server_results.keys() - submitted_ids:
            response = client.delete_historical_result(result_id, cookies=cookies)
            if response.status_code != 200:
                errors.append(f"delete result {result_id}: {response.json().get('error')}")

        for row in rows:
            fields = {field: row.get(field) or None for field in EDITABLE_FIELDS}

            if row.get("id"):
                try:
                    update = HistoricalResultUpdate(**fields)
                except ValidationError as exc:
                    errors.append(f"result {row['id']}: {exc.errors()[0]['msg']}")
                    continue
                response = client.update_historical_result(row["id"], update, cookies=cookies)
                if response.status_code != 200:
                    errors.append(f"result {row['id']}: {response.json().get('error')}")
                continue

            if not any(fields.values()):
                continue  # blank unsaved new row - silently skipped, matches old app

            try:
                data = HistoricalResultCreate(**fields)
            except ValidationError as exc:
                errors.append(f"new result: {exc.errors()[0]['msg']}")
                continue
            response = client.create_historical_result(data, cookies=cookies)
            if response.status_code != 201:
                errors.append(f"new result: {response.json().get('error')}")

        if errors:
            return html.Ul([html.Li(error) for error in errors])
        return "Saved."
