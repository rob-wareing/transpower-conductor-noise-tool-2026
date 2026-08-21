import dash_bootstrap_components as dbc
from dash import dcc, html


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
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(id="weather-wind-rose", figure={}), width=6),
                    dbc.Col(dcc.Graph(id="weather-monthly-rainfall", figure={}), width=6),
                ]
            ),
        ]
    )
