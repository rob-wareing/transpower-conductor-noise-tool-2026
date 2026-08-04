import dash_bootstrap_components as dbc
from dash import dcc, html


def content():
    return html.Div(
        [
            dcc.Interval(id="locations-init", interval=1000, n_intervals=0, max_intervals=1),
            dcc.Graph(id="locations-map", figure={}, style={"height": "600px"}),
            html.H4("Selected Site Information"),
            html.Div(
                id="selected-site-info",
                children="Click on a site marker to view information",
                style={"border": "1px solid #ccc", "padding": "10px"},
            ),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(id="locations-wind-rose", figure={}), width=6),
                    dbc.Col(dcc.Graph(id="locations-monthly-rainfall", figure={}), width=6),
                ]
            ),
        ]
    )
