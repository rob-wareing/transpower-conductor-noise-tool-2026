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

# The Sites box, shared shape across every Trends sub-tab and the Charts
# tab's own "Sites" panel (see layout/charts.py) - a dedicated
# dropdown-with-bulk-select box rather than inline with the other filters,
# since site selection is usually the first/most-used filter and benefits
# from more room.
SITES_CARD_STYLE = {
    "minWidth": "600px",
    "maxWidth": "650px",
    "minHeight": "500px",
    "flex": "1",
}
FILTER_ROW_STYLE = {
    "display": "flex",
    "flexWrap": "wrap",
    "gap": "1rem",
    "marginBottom": "1rem",
    "alignItems": "flex-start",
}


def _sites_card(dropdown_id, select_all_id, clear_id):
    return dbc.Card(
        [
            dbc.CardHeader("Sites"),
            dbc.CardBody(
                [
                    dcc.Dropdown(id=dropdown_id, multi=True, className="chart-site-select-wide"),
                    html.Div(
                        [
                            dbc.Button(
                                "Select all",
                                id=select_all_id,
                                color="secondary",
                                size="sm",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "Clear",
                                id=clear_id,
                                color="secondary",
                                outline=True,
                                size="sm",
                                n_clicks=0,
                            ),
                        ],
                        style={"display": "flex", "gap": "0.5rem", "marginTop": "0.75rem"},
                    ),
                ]
            ),
        ],
        style=SITES_CARD_STYLE,
    )


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
                                style={"marginBottom": "1rem"},
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
                                style={"marginBottom": "1rem"},
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
                                style={"marginBottom": "1rem"},
                            ),
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                    _sites_card(
                        "trends-rain-rate-site-select",
                        "trends-rain-rate-select-all-sites-button",
                        "trends-rain-rate-clear-sites-button",
                    ),
                ],
                style=FILTER_ROW_STYLE,
            ),
            html.Div(
                dbc.Button(
                    "Hide data",
                    id="trends-rain-rate-hide-data-button",
                    color="secondary",
                    size="sm",
                    n_clicks=0,
                ),
                style={"marginBottom": "0.5rem"},
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
                                style={"marginBottom": "1rem"},
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
                                style={"marginBottom": "1rem"},
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
                                style={"marginBottom": "1rem"},
                            ),
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                    _sites_card(
                        "trends-conductor-summary-site-select",
                        "trends-conductor-summary-select-all-sites-button",
                        "trends-conductor-summary-clear-sites-button",
                    ),
                ],
                style=FILTER_ROW_STYLE,
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
                                style={"marginBottom": "1rem"},
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
                                style={"marginBottom": "1rem"},
                            ),
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                    _sites_card(
                        "trends-age-effects-site-select",
                        "trends-age-effects-select-all-sites-button",
                        "trends-age-effects-clear-sites-button",
                    ),
                ],
                style=FILTER_ROW_STYLE,
            ),
            html.Div(
                dbc.Button(
                    "Hide data",
                    id="trends-age-effects-hide-data-button",
                    color="secondary",
                    size="sm",
                    n_clicks=0,
                ),
                style={"marginBottom": "0.5rem"},
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
