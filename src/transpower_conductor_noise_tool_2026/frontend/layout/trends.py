import dash_bootstrap_components as dbc
from dash import dcc, html

RAIN_RATE_VS_LEVEL_TAB_ID = "trends-rain-rate-vs-level"
AGE_EFFECTS_TAB_ID = "trends-age-effects"
CONDUCTOR_SUMMARY_TAB_ID = "trends-conductor-summary"

PLACEHOLDER_SUB_TABS = [
    ("Rain rate vs level", RAIN_RATE_VS_LEVEL_TAB_ID),
    ("Age effects", AGE_EFFECTS_TAB_ID),
]

DETECTION_LOGIC_OPTIONS = [
    {"label": "Original", "value": "original"},
    {"label": "Updated 2026", "value": "updated_2026"},
]

MEASUREMENT_DURATION_OPTIONS = [
    {"label": "1 minute", "value": 1},
    {"label": "15 minutes", "value": 15},
]


def _placeholder_panel(message):
    return html.Div(
        [html.P("Coming Soon"), html.P(message)],
        style={
            "height": "400px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "border": "2px dashed #ccc",
        },
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
                ],
                style={"display": "flex", "gap": "1rem", "marginBottom": "1rem"},
            ),
            dcc.Graph(id="trends-conductor-summary-chart"),
        ]
    )


def content():
    return html.Div(
        [
            html.H2("Trends Analysis"),
            html.P(
                "This tab is ready for trend analysis features to be implemented.",
                className="text-muted",
            ),
            dbc.Tabs(
                [
                    *[
                        dbc.Tab(
                            _placeholder_panel(f"{label} will be added here in a future update."),
                            label=label,
                            tab_id=tab_id,
                        )
                        for label, tab_id in PLACEHOLDER_SUB_TABS
                    ],
                    dbc.Tab(
                        _conductor_summary_panel(),
                        label="Conductor summary",
                        tab_id=CONDUCTOR_SUMMARY_TAB_ID,
                    ),
                ],
            ),
        ]
    )
