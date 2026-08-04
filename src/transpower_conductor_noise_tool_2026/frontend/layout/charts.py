import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from .table_styles import EDITABLE_CELL_HIGHLIGHT

# The date picker intentionally has no default start_date: refresh_charts
# treats an empty picker as "use the backend's default window" (see
# backend.domain.chart_service.DEFAULT_CHART_START_DATE). Setting a visual
# default here would make Dash fire the callback with an explicit start_date
# on every load, which would also change what _historical_dataframe splices
# into the overlay - so the mismatch between "picker looks empty" and "a
# default is still applied server-side" is deliberate, not an oversight.

CONDITION_OPTIONS = [
    {"label": "All", "value": "all"},
    {"label": "Wet", "value": "wet"},
    {"label": "Dry", "value": "dry"},
]

PARAMETER_OPTIONS = [
    {"label": "Leq adjusted", "value": "leq_adj"},
    {"label": "100Hz tone", "value": "tone_100hz"},
    {"label": "200Hz tone", "value": "tone_200hz"},
]

INTERVAL_WEEKS_OPTIONS = [{"label": f"{n} week{'s' if n != 1 else ''}", "value": n} for n in range(1, 5)]

MEASUREMENT_DURATION_OPTIONS = [
    {"label": "1 minute", "value": "1min"},
    {"label": "15 minutes", "value": "15min"},
]

DETECTION_LOGIC_OPTIONS = [
    {"label": "Original", "value": "original"},
    {"label": "Updated 2026", "value": "updated_2026"},
]

PLOT_BY_OPTIONS = [
    {"label": "Date", "value": "datetime"},
    {"label": "Days since conductoring", "value": "days_since_conductoring"},
]

TABLE_COLUMN_DEFS = [
    ("Site ID", "noise_site_id", "numeric", False),
    ("Site name", "site_name", "text", False),
    ("Datetime", "datetime", "datetime", False),
    ("Conductor and treatment", "conductor_and_treatment", "text", False),
    ("Grease", "grease", "text", False),
    ("Days since conductoring", "days_since_conductoring", "numeric", False),
    ("Leq_adj (dB)", "leq_adj", "numeric", False),
    ("100Hz tone (dB)", "tone_100hz", "numeric", False),
    ("200Hz tone (dB)", "tone_200hz", "numeric", False),
    ("Rain 1 (mm)", "rain1", "numeric", False),
    ("Rain 2 (mm)", "rain2", "numeric", False),
    ("Wet", "is_wet", "text", True),
    ("Include", "include", "text", True),
]


def content(write_access: bool = False):
    table_columns = [
        {
            "name": name,
            "id": col_id,
            "type": col_type,
            "editable": write_access and always_editable,
        }
        for name, col_id, col_type, always_editable in TABLE_COLUMN_DEFS
    ]
    button_style = {} if write_access else {"display": "none"}

    return html.Div(
        [
            dcc.Interval(id="chart-init", interval=1000, n_intervals=0, max_intervals=1),
            html.Div(
                [
                    # Row 1: Sites, Date range
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Sites"),
                                    dcc.Dropdown(id="chart-site-select", multi=True),
                                ],
                                style={"minWidth": "500px", "maxWidth": "900px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Date range"),
                                    dcc.DatePickerRange(id="chart-date-range"),
                                ]
                            ),
                        ],
                        style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
                    ),
                    # Row 2: Condition, Parameter, Aggregation period
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Condition"),
                                    dcc.Dropdown(
                                        id="chart-condition",
                                        options=CONDITION_OPTIONS,
                                        value="all",
                                    ),
                                ],
                                style={"minWidth": "150px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Parameter"),
                                    dcc.Dropdown(
                                        id="chart-parameter",
                                        options=PARAMETER_OPTIONS,
                                        value="tone_100hz",
                                    ),
                                ],
                                style={"minWidth": "180px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Aggregation period"),
                                    dcc.Dropdown(
                                        id="chart-interval-weeks",
                                        options=INTERVAL_WEEKS_OPTIONS,
                                        value=2,
                                        clearable=False,
                                    ),
                                ],
                                style={"minWidth": "160px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Measurement duration"),
                                    dcc.Dropdown(
                                        id="chart-measurement-duration",
                                        options=MEASUREMENT_DURATION_OPTIONS,
                                        value="15min",
                                        clearable=False,
                                    ),
                                ],
                                style={"minWidth": "180px"},
                            ),
                        ],
                        style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
                    ),
                    # Row 3: Conductor and treatment, Grease
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Conductor and treatment"),
                                    dcc.Dropdown(
                                        id="chart-conductor-treatment",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        placeholder="All",
                                    ),
                                ],
                                style={"minWidth": "400px", "maxWidth": "700px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Grease"),
                                    dcc.Dropdown(
                                        id="chart-grease",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        placeholder="All",
                                    ),
                                ],
                                style={"minWidth": "350px", "maxWidth": "600px"},
                            ),
                        ],
                        style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
                    ),
                    # Row 4: Detection logic, Plot by
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Detection logic"),
                                    dcc.Dropdown(
                                        id="chart-detection-logic",
                                        options=DETECTION_LOGIC_OPTIONS,
                                    ),
                                ],
                                style={"minWidth": "220px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Plot by"),
                                    dcc.RadioItems(
                                        id="chart-plot-by",
                                        options=PLOT_BY_OPTIONS,
                                        value="datetime",
                                    ),
                                ],
                                style={"minWidth": "220px"},
                            ),
                            html.Div(
                                [
                                    dbc.Switch(
                                        id="chart-show-historical",
                                        label="Show historical",
                                        value=False,
                                    ),
                                ],
                                style={"minWidth": "180px", "alignSelf": "flex-end"},
                            ),
                        ],
                        style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
                    ),
                ],
                style={"marginBottom": "1rem"},
            ),
            html.Div(
                dbc.Button(
                    "Export plot data",
                    id="chart-export-plot-button",
                    color="primary",
                    size="sm",
                    n_clicks=0,
                ),
                style={"marginBottom": "0.5rem"},
            ),
            dcc.Graph(id="noise-chart"),
            html.H4("Data Availability Timeline"),
            dcc.Graph(id="timeline-chart"),
            html.Div(
                [
                    dbc.Button(
                        "Expand table",
                        id="chart-toggle-table-button",
                        color="secondary",
                        size="sm",
                        n_clicks=0,
                    ),
                ],
                style={"display": "flex", "justifyContent": "flex-end", "marginTop": "1rem"},
            ),
            dbc.Collapse(
                id="chart-table-collapse",
                is_open=False,
                children=[
                    dash_table.DataTable(
                        id="chart-table",
                        columns=table_columns,
                        data=[],
                        page_size=25,
                        sort_action="native",
                        editable=write_access,
                        style_data_conditional=EDITABLE_CELL_HIGHLIGHT,
                    ),
                    html.Div(
                        [
                            dbc.Button(
                                "Save changes",
                                id="chart-table-save-button",
                                color="success",
                                n_clicks=0,
                                style=button_style,
                            ),
                            dbc.Button(
                                "Export table data",
                                id="chart-export-table-button",
                                color="primary",
                                n_clicks=0,
                            ),
                        ],
                        style={"display": "flex", "gap": "0.5rem", "marginTop": "0.5rem"},
                    ),
                    html.Div(id="chart-table-status"),
                ],
            ),
            dcc.Download(id="chart-download-table"),
            dcc.Download(id="chart-download-plot"),
        ]
    )
