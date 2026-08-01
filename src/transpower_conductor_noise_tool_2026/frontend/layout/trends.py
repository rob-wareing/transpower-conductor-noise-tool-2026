import dash_bootstrap_components as dbc
from dash import html

SUB_TABS = [
    ("Rain rate vs level", "trends-rain-rate-vs-level"),
    ("Age effects", "trends-age-effects"),
    ("Conductor summary", "trends-conductor-summary"),
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
                    dbc.Tab(
                        _placeholder_panel(f"{label} will be added here in a future update."),
                        label=label,
                        tab_id=tab_id,
                    )
                    for label, tab_id in SUB_TABS
                ],
            ),
        ]
    )
