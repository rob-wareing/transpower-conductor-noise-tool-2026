import dash_bootstrap_components as dbc
from dash import dcc, html

RAIN_RATE_VS_LEVEL_TAB_ID = "trends-rain-rate-vs-level"
AGE_EFFECTS_TAB_ID = "trends-age-effects"
CONDUCTOR_SUMMARY_TAB_ID = "trends-conductor-summary"

DETECTION_LOGIC_OPTIONS = [
    {"label": "Original", "value": "original"},
    {"label": "Updated 2026", "value": "updated_2026"},
]

MEASUREMENT_DURATION_OPTIONS = [
    {"label": "1 minute", "value": 1},
    {"label": "15 minutes", "value": 15},
]

METRIC_OPTIONS = [
    {"label": "L90", "value": "l90"},
    {"label": "100Hz tone", "value": "tone_100hz"},
    {"label": "200Hz tone", "value": "tone_200hz"},
]

INCLUDE_DRY_OPTIONS = [
    {"label": "True", "value": True},
    {"label": "False", "value": False},
]


def _rain_rate_vs_level_panel():
    return html.Div(
        [
            dcc.Interval(
                id="trends-rain-rate-init", interval=1000, n_intervals=0, max_intervals=1
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Detection logic"),
                            dcc.Dropdown(
                                id="trends-rain-rate-detection-logic",
                                options=DETECTION_LOGIC_OPTIONS,
                                value="original",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "220px"},
                    ),
                    html.Div(
                        [
                            html.Label("Metric"),
                            dcc.Dropdown(
                                id="trends-rain-rate-metric",
                                options=METRIC_OPTIONS,
                                value="l90",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Sites"),
                            dcc.Dropdown(id="trends-rain-rate-site-select", multi=True),
                        ],
                        style={"minWidth": "400px", "maxWidth": "700px"},
                    ),
                    html.Div(
                        [
                            html.Label("Include dry"),
                            dcc.Dropdown(
                                id="trends-rain-rate-include-dry",
                                options=INCLUDE_DRY_OPTIONS,
                                value=False,
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "130px"},
                    ),
                ],
                style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
            ),
            dcc.Graph(id="trends-rain-rate-chart"),
        ]
    )


def _conductor_summary_panel():
    return html.Div(
        [
            dcc.Interval(
                id="trends-conductor-summary-init", interval=1000, n_intervals=0, max_intervals=1
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Metric"),
                            dcc.Dropdown(
                                id="trends-conductor-summary-metric",
                                options=METRIC_OPTIONS,
                                value="l90",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Detection logic"),
                            dcc.Dropdown(
                                id="trends-conductor-summary-detection-logic",
                                options=DETECTION_LOGIC_OPTIONS,
                                value="original",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "220px"},
                    ),
                    html.Div(
                        [
                            html.Label("Measurement duration"),
                            dcc.Dropdown(
                                id="trends-conductor-summary-duration",
                                options=MEASUREMENT_DURATION_OPTIONS,
                                value=15,
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Sites"),
                            dcc.Dropdown(id="trends-conductor-summary-site-select", multi=True),
                        ],
                        style={"minWidth": "400px", "maxWidth": "700px"},
                    ),
                ],
                style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
            ),
            dcc.Graph(id="trends-conductor-summary-chart"),
        ]
    )


def _age_effects_panel():
    return html.Div(
        [
            dcc.Interval(
                id="trends-age-effects-init", interval=1000, n_intervals=0, max_intervals=1
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Detection logic"),
                            dcc.Dropdown(
                                id="trends-age-effects-detection-logic",
                                options=DETECTION_LOGIC_OPTIONS,
                                value="original",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "220px"},
                    ),
                    html.Div(
                        [
                            html.Label("Metric"),
                            dcc.Dropdown(
                                id="trends-age-effects-metric",
                                options=METRIC_OPTIONS,
                                value="l90",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Sites"),
                            dcc.Dropdown(id="trends-age-effects-site-select", multi=True),
                        ],
                        style={"minWidth": "400px", "maxWidth": "700px"},
                    ),
                ],
                style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
            ),
            dcc.Graph(id="trends-age-effects-chart"),
        ]
    )


def content():
    return html.Div(
        [
            html.H2("Trends Analysis"),
            html.P(
                "General trends analysis.",
                className="text-muted",
            ),
            dbc.Tabs(
                [
                    dbc.Tab(
                        _rain_rate_vs_level_panel(),
                        label="Rain rate vs level",
                        tab_id=RAIN_RATE_VS_LEVEL_TAB_ID,
                    ),
                    dbc.Tab(
                        _age_effects_panel(),
                        label="Age effects",
                        tab_id=AGE_EFFECTS_TAB_ID,
                    ),
                    dbc.Tab(
                        _conductor_summary_panel(),
                        label="Conductor summary",
                        tab_id=CONDUCTOR_SUMMARY_TAB_ID,
                    ),
                ],
            ),
        ]
    )
