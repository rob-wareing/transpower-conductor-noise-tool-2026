from dash import html


def content():
    return html.Div(
        [
            html.H2("Trends Analysis"),
            html.P(
                "This tab is ready for trend analysis features to be implemented.",
                className="text-muted",
            ),
            html.Div(
                [
                    html.P("Coming Soon"),
                    html.P("Trend analysis functionality will be added here in future updates."),
                ],
                style={
                    "height": "400px",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "border": "2px dashed #ccc",
                },
            ),
        ]
    )
