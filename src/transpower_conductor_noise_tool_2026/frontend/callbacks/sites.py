import flask
import pandas as pd
from dash import Input, Output, State, dcc, html, no_update
from pydantic import ValidationError

from transpower_conductor_noise_tool_2026.shared.contracts import SiteUpdate

from ..client import BackendClient

EDITABLE_FIELDS = [
    "site_code",
    "plot_color",
    "height_adj_db",
    "data_folder",
    "report_folder",
    "latitude",
    "longitude",
]


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("sites-table", "data"),
        Input("sites-init", "n_intervals"),
        Input("sites-status", "children"),
    )
    def refresh_sites_table(_n_intervals, _status):
        if client is None:
            return []
        return [site.model_dump() for site in client.get_site_details()]

    @dash_app.callback(
        Output("sites-status", "children"),
        Input("sites-save-button", "n_clicks"),
        State("sites-table", "data"),
        prevent_initial_call=True,
    )
    def save_sites(n_clicks, rows):
        if not n_clicks or client is None:
            return ""

        errors = []
        for row in rows:
            try:
                update = SiteUpdate(**{field: row.get(field) for field in EDITABLE_FIELDS})
            except ValidationError as exc:
                errors.append(f"site {row['noise_site_id']}: {exc.errors()[0]['msg']}")
                continue
            response = client.update_site(
                row["noise_site_id"], update, cookies=flask.request.cookies
            )
            if response.status_code != 200:
                errors.append(f"site {row['noise_site_id']}: {response.json().get('error')}")

        if errors:
            return html.Ul([html.Li(error) for error in errors])
        return "Saved."

    @dash_app.callback(
        Output("sites-download", "data"),
        Input("sites-export-button", "n_clicks"),
        State("sites-table", "data"),
        prevent_initial_call=True,
    )
    def export_sites(n_clicks, rows):
        if not n_clicks or not rows:
            return no_update
        return dcc.send_data_frame(pd.DataFrame(rows).to_csv, "sites.csv", index=False)
