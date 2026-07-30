from dash import dcc, html

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


def content():
    return html.Div(
        [
            dcc.Interval(id="chart-init", interval=1000, n_intervals=0, max_intervals=1),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Sites"),
                            dcc.Dropdown(id="chart-site-select", multi=True),
                        ],
                        style={"minWidth": "250px"},
                    ),
                    html.Div(
                        [
                            html.Label("Date range"),
                            dcc.DatePickerRange(id="chart-date-range"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("Condition"),
                            dcc.Dropdown(
                                id="chart-condition", options=CONDITION_OPTIONS, value="all"
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
                ],
                style={"display": "flex", "gap": "1rem", "flexWrap": "wrap", "marginBottom": "1rem"},
            ),
            dcc.Graph(id="noise-chart"),
            html.H4("Data Availability Timeline"),
            dcc.Graph(id="timeline-chart"),
        ]
    )
