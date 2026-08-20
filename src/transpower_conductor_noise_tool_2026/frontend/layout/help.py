import dash_bootstrap_components as dbc
from dash import html

DETECTION_LOGIC_CRITERIA = [
    ("Time", "22:00-07:00", "22:00-05:00"),
    (
        "Rain",
        "Wet if this or the previous reading had rain > 0",
        "Wet if this reading's rain >= 0.05 mm (previous reading no longer counted)",
    ),
    ("Wind", "Wind speed <= 2.0 m/s", "Wind speed < 1.5 m/s"),
    ("Leq-L90", "Excluded if (Leq - L90) > 2.0 dB", "No Leq-L90 check (removed)"),
    (
        "RMSE of Leq",
        "Not checked",
        "Excluded if RMSE of the 1-second Leq trace > 0.75 (rows with no RMSE data still pass)",
    ),
    ("Line status", "Not checked", "Live"),
    (
        "Rain and wind measurement",
        "No explicit check (a missing reading fails the Wind/Rain checks above by comparison)",
        "Row dropped outright if either wind speed or rain is missing",
    ),
]


def _section(title, paragraphs, extra_children=None):
    return html.Div(
        [
            html.H4(title),
            *[html.P(paragraph) for paragraph in paragraphs],
            *(extra_children or []),
        ],
        className="mb-4",
    )


def _detection_logic_table():
    header = html.Thead(
        html.Tr([html.Th("Criteria"), html.Th("Original"), html.Th("Updated 2026")])
    )
    body = html.Tbody(
        [
            html.Tr([html.Td(criteria), html.Td(pre_2026), html.Td(updated)])
            for criteria, pre_2026, updated in DETECTION_LOGIC_CRITERIA
        ]
    )
    return dbc.Table(
        [header, body],
        bordered=True,
        hover=True,
        responsive=True,
        className="mb-4",
    )


def content():
    return html.Div(
        [
            html.H2("Help"),
            _section(
                "Detection Logic",
                [
                    "Every reading is processed twice, by two independent rule sets, "
                    "and both results are kept side by side in the database under the columns: "
                    "“Original” and “Updated 2026”.",
                    "Use the “Detection logic” dropdown on the Charts and Trends tabs to "
                    "switch between the two - they will generally show different numbers of "
                    "qualifying readings and slightly different levels for the same site and "
                    "date range, since they're not filtering the same way.",
                ],
                extra_children=[_detection_logic_table()],
            ),
            _section(
                "Historical Data",
                [
                    "XX.",
                ],
            ),
            _section(
                "Wind Roses",
                [
                    "On the Locations tab, clicking a site marker shows a wind rose for that "
                    "site: a compass-style chart with 16 direction sectors, where each sector's "
                    "length shows how often the wind blew from that direction and its colour "
                    "shows the average wind speed when it did.",
                    "The wind rose is built from that site's full weather history and is "
                    "refreshed automatically each week, so it may lag a few days behind the "
                    "latest readings.",
                ],
            ),
            _section(
                "Site Location",
                [
                    "The Locations tab shows every site on a map. Click a marker to see that "
                    "site's basic details, along with its wind rose and its average monthly "
                    "rainfall chart below the map.",
                    "The monthly rainfall chart shows one average figure per calendar month "
                    "(January through December) calculated across that site's full weather "
                    "history, so it reflects typical seasonal rainfall rather than any single "
                    "year.",
                ],
            ),
        ]
    )
