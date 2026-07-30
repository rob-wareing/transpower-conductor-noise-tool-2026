from dash import dash_table, dcc, html

ALWAYS_READONLY_COLUMNS = {"noise_site_id", "site_name"}

COLUMN_DEFS = [
    ("Site ID", "noise_site_id", "numeric"),
    ("Site name", "site_name", "text"),
    ("Site code", "site_code", "text"),
    ("Plot colour", "plot_color", "text"),
    ("Height adjustment (dB)", "height_adj_db", "numeric"),
    ("Data folder", "data_folder", "text"),
    ("Report folder", "report_folder", "text"),
    ("Latitude", "latitude", "numeric"),
    ("Longitude", "longitude", "numeric"),
]


def content(write_access: bool = False):
    columns = [
        {
            "name": name,
            "id": col_id,
            "type": col_type,
            "editable": write_access and col_id not in ALWAYS_READONLY_COLUMNS,
        }
        for name, col_id, col_type in COLUMN_DEFS
    ]

    return html.Div(
        [
            dcc.Interval(id="sites-init", interval=1000, n_intervals=0, max_intervals=1),
            dash_table.DataTable(id="sites-table", columns=columns, data=[]),
            html.Button(
                "Save changes",
                id="sites-save-button",
                n_clicks=0,
                style={} if write_access else {"display": "none"},
            ),
            html.Button("Export CSV", id="sites-export-button", n_clicks=0),
            dcc.Download(id="sites-download"),
            html.Div(id="sites-status"),
        ]
    )
