from dash import dash_table, dcc, html

COLUMN_DEFS = [
    ("Site ID", "noise_site_id", "numeric"),
    ("Outage type", "outage_type", "text"),
    ("Start datetime", "start_datetime", "text"),
    ("End datetime", "end_datetime", "text"),
    ("Notes", "notes", "text"),
]


def content(write_access: bool = False):
    columns = [
        {
            "name": name,
            "id": col_id,
            "type": col_type,
            "editable": write_access,
            **({"presentation": "dropdown"} if col_id == "outage_type" else {}),
        }
        for name, col_id, col_type in COLUMN_DEFS
    ]

    button_style = {} if write_access else {"display": "none"}

    return html.Div(
        [
            dcc.Interval(id="outages-init", interval=1000, n_intervals=0, max_intervals=1),
            dash_table.DataTable(
                id="outages-table",
                columns=columns,
                data=[],
                row_deletable=write_access,
                editable=write_access,
            ),
            html.Button("Add row", id="outages-add-row-button", n_clicks=0, style=button_style),
            html.Button(
                "Save changes", id="outages-save-button", n_clicks=0, style=button_style
            ),
            html.Button("Export CSV", id="outages-export-button", n_clicks=0),
            dcc.Download(id="outages-download"),
            html.Div(id="outages-status"),
        ]
    )
