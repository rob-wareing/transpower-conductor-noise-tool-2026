import flask
import pandas as pd
from dash import Input, Output, State, dcc, html, no_update
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import OutageCreate, OutageUpdate

from ..client import BackendClient

EDITABLE_FIELDS = ["noise_site_id", "outage_type", "start_datetime", "end_datetime", "notes"]

# Set only on rows that failed to save; layout/outages.py highlights any row
# that has it (style_data_conditional "is str"), and the column itself is only
# added to the table while there are failed rows to show.
SAVE_ERROR_FIELD = "save_error"
SAVE_ERROR_COLUMN = {"name": "Save error", "id": SAVE_ERROR_FIELD, "editable": False}


def _error_message(response):
    # The backend returns {"error": ...} as JSON for expected failures (a
    # string, or a list of pydantic error dicts for validation errors); an
    # unexpected server error comes back as an HTML page instead.
    try:
        error = response.json().get("error")
    except ValueError:
        return f"server error (HTTP {response.status_code})"
    if isinstance(error, list) and error and isinstance(error[0], dict):
        return error[0].get("msg", str(error[0]))
    return str(error)


def _with_save_error(row, reason):
    return {**row, SAVE_ERROR_FIELD: reason}


def _without_save_error_column(columns):
    return [column for column in columns if column["id"] != SAVE_ERROR_FIELD]


def _with_save_error_column(columns):
    return _without_save_error_column(columns) + [SAVE_ERROR_COLUMN]


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("outages-table", "dropdown"),
        Input("outages-init", "n_intervals"),
    )
    def populate_outage_type_options(n_intervals):
        # Dash also runs this on the initial render (n_intervals=0); only load
        # once the tab's init interval has actually fired - see tab_loading.py.
        if not n_intervals:
            return no_update
        if client is None:
            return {}
        options = [{"label": t, "value": t} for t in client.get_outage_types()]
        return {"outage_type": {"options": options}}

    @dash_app.callback(
        Output("outages-table", "data"),
        Output("outages-loaded-ids", "data"),
        Input("outages-init", "n_intervals"),
    )
    def refresh_outages_table(n_intervals):
        # Dash also runs this on the initial render (n_intervals=0); only load
        # once the tab's init interval has actually fired - see tab_loading.py.
        if not n_intervals:
            return no_update, no_update
        if client is None:
            return [], []
        rows = [outage.model_dump(mode="json") for outage in client.get_outages()]
        return rows, [row["id"] for row in rows]

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
        Output("outages-table", "data", allow_duplicate=True),
        Output("outages-table", "columns"),
        Output("outages-loaded-ids", "data", allow_duplicate=True),
        Input("outages-save-button", "n_clicks"),
        State("outages-table", "data"),
        State("outages-loaded-ids", "data"),
        State("outages-table", "columns"),
        prevent_initial_call=True,
    )
    def save_outages(n_clicks, rows, loaded_ids, columns):
        if not n_clicks or client is None:
            return "", no_update, no_update, no_update

        cookies = flask.request.cookies
        submitted_ids = {row["id"] for row in rows if row.get("id")}

        errors = []
        # Rows that didn't save, kept in the table (with the user's values and
        # the reason) instead of vanishing when the table reloads below.
        failed_updates = {}  # outage id -> submitted row + save_error
        failed_new_rows = []
        failed_deletes = {}  # outage id -> reason; the row stays on the server

        # Only delete rows that were in this table when it was loaded and the
        # user has since removed - not every server row missing from the
        # browser's copy, which would also delete rows other users added
        # after this table was loaded.
        for outage_id in set(loaded_ids or []) - submitted_ids:
            response = client.delete_outage(outage_id, cookies=cookies)
            if response.status_code == 404:
                continue  # already deleted elsewhere - the outcome the user wanted
            if response.status_code != 200:
                reason = _error_message(response)
                errors.append(f"delete outage {outage_id}: {reason}")
                failed_deletes[outage_id] = f"delete failed: {reason}"

        for row in rows:
            fields = {field: row.get(field) or None for field in EDITABLE_FIELDS}

            if row.get("id"):
                try:
                    update = OutageUpdate(**fields)
                except ValidationError as exc:
                    reason = exc.errors()[0]["msg"]
                else:
                    response = client.update_outage(row["id"], update, cookies=cookies)
                    if response.status_code == 200:
                        continue
                    reason = _error_message(response)
                errors.append(f"outage {row['id']}: {reason}")
                failed_updates[row["id"]] = _with_save_error(row, reason)
                continue

            if not any(fields.values()):
                continue  # blank unsaved new row - silently skipped, matches old app

            try:
                data = OutageCreate(**fields)
            except ValidationError as exc:
                reason = exc.errors()[0]["msg"]
            else:
                response = client.create_outage(data, cookies=cookies)
                if response.status_code == 201:
                    continue
                reason = _error_message(response)
            errors.append(f"new outage: {reason}")
            failed_new_rows.append(_with_save_error(row, reason))

        server_rows = [outage.model_dump(mode="json") for outage in client.get_outages()]
        table_rows = [
            failed_updates.get(row["id"])
            or (
                _with_save_error(row, failed_deletes[row["id"]])
                if row["id"] in failed_deletes
                else row
            )
            for row in server_rows
        ]
        # A failed update whose row is no longer on the server (deleted by
        # someone else meanwhile) still needs showing, alongside new rows.
        server_ids = {row["id"] for row in server_rows}
        table_rows += [row for outage_id, row in failed_updates.items() if outage_id not in server_ids]
        table_rows += failed_new_rows
        loaded = [row["id"] for row in server_rows]

        if errors:
            status = html.Div(
                [
                    html.P(
                        "Some rows didn't save. They're highlighted in the table with the "
                        "reason in the Save error column - fix them and save again."
                    ),
                    html.Ul([html.Li(error) for error in errors]),
                ]
            )
            return status, table_rows, _with_save_error_column(columns), loaded
        return "Saved.", table_rows, _without_save_error_column(columns), loaded

    @dash_app.callback(
        Output("outages-download", "data"),
        Input("outages-export-button", "n_clicks"),
        State("outages-table", "data"),
        prevent_initial_call=True,
    )
    def export_outages(n_clicks, rows):
        if not n_clicks or not rows:
            return no_update
        return dcc.send_data_frame(pd.DataFrame(rows).to_csv, "outages.csv", index=False)
