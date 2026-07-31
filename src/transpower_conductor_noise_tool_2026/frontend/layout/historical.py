import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from .table_styles import EDITABLE_CELL_HIGHLIGHT

COLUMN_DEFS = [
    ("Site ID", "noise_site_id", "numeric"),
    ("Period end date", "period_end_date", "text"),
    ("Leq_adj (dB)", "leq_adj", "numeric"),
    ("100Hz tone (dB)", "tone_100hz", "numeric"),
]


def content(write_access: bool = False):
    columns = [
        {"name": name, "id": col_id, "type": col_type, "editable": write_access}
        for name, col_id, col_type in COLUMN_DEFS
    ]

    button_style = {} if write_access else {"display": "none"}

    return html.Div(
        [
            dcc.Interval(id="historical-init", interval=1000, n_intervals=0, max_intervals=1),
            dash_table.DataTable(
                id="historical-table",
                columns=columns,
                data=[],
                page_size=20,
                sort_action="native",
                row_deletable=write_access,
                editable=write_access,
                style_data_conditional=EDITABLE_CELL_HIGHLIGHT,
            ),
            dbc.Button(
                "Add row",
                id="historical-add-row-button",
                color="secondary",
                n_clicks=0,
                style=button_style,
            ),
            dbc.Button(
                "Save changes",
                id="historical-save-button",
                color="success",
                n_clicks=0,
                style=button_style,
            ),
            dbc.Button(
                "Export CSV", id="historical-export-button", color="primary", n_clicks=0
            ),
            dcc.Download(id="historical-download"),
            html.Div(id="historical-status"),
        ]
    )
