import flask
from dash import Input, Output, State, html
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import OutageCreate, OutageUpdate

from ..client import BackendClient

EDITABLE_FIELDS = ["noise_site_id", "outage_type", "start_datetime", "end_datetime", "notes"]


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("outages-table", "dropdown"),
        Input("outages-init", "n_intervals"),
    )
    def populate_outage_type_options(_n_intervals):
        if client is None:
            return {}
        options = [{"label": t, "value": t} for t in client.get_outage_types()]
        return {"outage_type": {"options": options}}

    @dash_app.callback(
        Output("outages-table", "data"),
        Input("outages-init", "n_intervals"),
        Input("outages-status", "children"),
    )
    def refresh_outages_table(_n_intervals, _status):
        if client is None:
            return []
        return [outage.model_dump(mode="json") for outage in client.get_outages()]

    @dash_app.callback(
        Output("outages-table", "data", allow_duplicate=True),
        Input("outages-add-row-button", "n_clicks"),
        State("outages-table", "data"),
        prevent_initial_call=True,
    )
    def add_row(n_clicks, rows):
        if not n_clicks:
            return rows
        return rows + [{field: "" for field in EDITABLE_FIELDS}]

    @dash_app.callback(
        Output("outages-status", "children"),
        Input("outages-save-button", "n_clicks"),
        State("outages-table", "data"),
        prevent_initial_call=True,
    )
    def save_outages(n_clicks, rows):
        if not n_clicks or client is None:
            return ""

        cookies = flask.request.cookies
        server_outages = {outage.id: outage for outage in client.get_outages()}
        submitted_ids = {row["id"] for row in rows if row.get("id")}

        errors = []

        for outage_id in server_outages.keys() - submitted_ids:
            response = client.delete_outage(outage_id, cookies=cookies)
            if response.status_code != 200:
                errors.append(f"delete outage {outage_id}: {response.json().get('error')}")

        for row in rows:
            fields = {field: row.get(field) or None for field in EDITABLE_FIELDS}

            if row.get("id"):
                try:
                    update = OutageUpdate(**fields)
                except ValidationError as exc:
                    errors.append(f"outage {row['id']}: {exc.errors()[0]['msg']}")
                    continue
                response = client.update_outage(row["id"], update, cookies=cookies)
                if response.status_code != 200:
                    errors.append(f"outage {row['id']}: {response.json().get('error')}")
                continue

            if not any(fields.values()):
                continue  # blank unsaved new row - silently skipped, matches old app

            try:
                data = OutageCreate(**fields)
            except ValidationError as exc:
                errors.append(f"new outage: {exc.errors()[0]['msg']}")
                continue
            response = client.create_outage(data, cookies=cookies)
            if response.status_code != 201:
                errors.append(f"new outage: {response.json().get('error')}")

        if errors:
            return html.Ul([html.Li(error) for error in errors])
        return "Saved."
