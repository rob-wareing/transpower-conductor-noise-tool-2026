from datetime import datetime

import dash_bootstrap_components as dbc
from dash import dcc, html

# Fixed, generous lower bound rather than derived from any data query - this
# is a plain client-side dropdown, not backed by a "what years actually have
# data" lookup, so it just needs to comfortably cover the site network's
# history.
EARLIEST_YEAR = 2016

# Matches callbacks.locations.MONTH_LABELS - duplicated rather than imported
# to keep layout modules independent of the callbacks layer.
MONTH_OPTIONS = [
    {"label": label, "value": index + 1}
    for index, label in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    )
]


def _year_options():
    current_year = datetime.now().year
    return [{"label": str(year), "value": year} for year in range(EARLIEST_YEAR, current_year + 1)]


def _month_year_picker(label, month_id, year_id):
    return html.Div(
        [
            html.Label(label),
            html.Div(
                [
                    dcc.Dropdown(
                        id=month_id,
                        options=MONTH_OPTIONS,
                        placeholder="Month",
                        style={"minWidth": "140px"},
                    ),
                    dcc.Dropdown(
                        id=year_id,
                        options=_year_options(),
                        placeholder="Year",
                        style={"minWidth": "110px"},
                    ),
                ],
                style={"display": "flex", "gap": "0.5rem"},
            ),
        ]
    )


def content():
    return html.Div(
        [
            dcc.Interval(id="weather-init", interval=1000, n_intervals=0, max_intervals=1),
            html.Div(
                [
                    html.Label("Sites"),
                    dcc.Dropdown(id="weather-site-select", placeholder="Select a site"),
                ],
                style={"maxWidth": "500px", "marginBottom": "1rem"},
            ),
            html.Div(
                [
                    _month_year_picker("Start", "weather-start-month", "weather-start-year"),
                    _month_year_picker("End", "weather-end-month", "weather-end-year"),
                ],
                style={"display": "flex", "gap": "1.5rem", "marginBottom": "1rem", "flexWrap": "wrap"},
            ),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(id="weather-wind-rose", figure={}), width=6),
                    dbc.Col(dcc.Graph(id="weather-monthly-rainfall", figure={}), width=6),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(id="weather-rainfall-stats", figure={}), width=6),
                    dbc.Col(dcc.Graph(id="weather-windspeed-stats", figure={}), width=6),
                ]
            ),
        ]
    )
