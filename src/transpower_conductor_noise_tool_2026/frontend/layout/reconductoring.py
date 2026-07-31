import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from .table_styles import EDITABLE_CELL_HIGHLIGHT

COLUMN_DEFS = [
    ("Site ID", "noise_site_id", "numeric"),
    ("Conductor and treatment", "conductor_and_treatment", "text"),
    ("Grease", "grease", "text"),
    ("Reconductoring date", "reconductoring_date", "text"),
    ("Notes", "notes", "text"),
]


def content(write_access: bool = False):
    columns = [
        {"name": name, "id": col_id, "type": col_type, "editable": write_access}
        for name, col_id, col_type in COLUMN_DEFS
    ]

    button_style = {} if write_access else {"display": "none"}

    return html.Div(
        [
            dcc.Interval(
                id="reconductoring-init", interval=1000, n_intervals=0, max_intervals=1
            ),
            dash_table.DataTable(
                id="reconductoring-table",
                columns=columns,
                data=[],
                row_deletable=write_access,
                editable=write_access,
                style_data_conditional=EDITABLE_CELL_HIGHLIGHT,
            ),
            dbc.Button(
                "Add row",
                id="reconductoring-add-row-button",
                color="secondary",
                n_clicks=0,
                style=button_style,
            ),
            dbc.Button(
                "Save changes",
                id="reconductoring-save-button",
                color="success",
                n_clicks=0,
                style=button_style,
            ),
            dbc.Button(
                "Export CSV", id="reconductoring-export-button", color="primary", n_clicks=0
            ),
            dcc.Download(id="reconductoring-download"),
            html.Div(id="reconductoring-status"),
        ]
    )
