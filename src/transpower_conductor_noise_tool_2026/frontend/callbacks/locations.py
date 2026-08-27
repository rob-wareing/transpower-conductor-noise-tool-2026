import plotly.graph_objects as go
from dash import Input, Output, html

from ..client import BackendClient

DEFAULT_CENTER = {"lat": -41.0, "lon": 174.9}

# Canonical 16-point compass order, matching
# backend.persistence.repositories.reading_repository.DIRECTION_SECTORS.
DIRECTION_SECTORS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]
MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def _empty_figure(message):
    figure = go.Figure()
    figure.update_layout(
        annotations=[{"text": message, "showarrow": False, "font": {"size": 14}}],
        xaxis={"visible": False},
        yaxis={"visible": False},
        height=400,
    )
    return figure


def _site_id_from_click(click_data):
    if not click_data:
        return None
    return click_data["points"][0].get("customdata", {}).get("id")


def _build_wind_rose_figure(sectors):
    by_sector = {sector.direction_sector: sector for sector in sectors}
    counts = [by_sector[s].sample_count if s in by_sector else 0 for s in DIRECTION_SECTORS]
    speeds = [by_sector[s].avg_wind_speed if s in by_sector else 0 for s in DIRECTION_SECTORS]

    figure = go.Figure(
        go.Barpolar(
            r=counts,
            theta=DIRECTION_SECTORS,
            marker=dict(color=speeds, colorscale="Viridis", colorbar=dict(title="Avg speed (m/s)")),
            hovertemplate="%{theta}: %{r} readings<extra></extra>",
        )
    )
    figure.update_layout(
        title="Wind Rose",
        polar=dict(angularaxis=dict(direction="clockwise", rotation=90)),
        height=400,
    )
    return figure


def _build_monthly_rainfall_figure(months):
    # total_rain (summed across every year of history for that month), not
    # avg_rain_mm (a single reading's average) - avg_rain_mm is still
    # computed and stored (see monthly_rainfall_repository.py) but no longer
    # charted here.
    by_month = {row.month: row for row in months}
    values = [by_month[m].total_rain if m in by_month else 0 for m in range(1, 13)]

    figure = go.Figure(go.Bar(x=MONTH_LABELS, y=values))
    figure.update_layout(
        title="Total Monthly Rainfall",
        yaxis_title="Rain (mm)",
        height=400,
    )
    return figure


def _event_table(headers, rows, empty_message):
    if not rows:
        return html.P(empty_message)
    return html.Table(
        [html.Thead(html.Tr([html.Th(header) for header in headers]))]
        + [html.Tbody([html.Tr([html.Td(cell) for cell in row]) for row in rows])],
        style={"width": "100%", "marginBottom": "1rem"},
    )


def _build_site_activity_panel(summary):
    # .model_dump(mode="json") first, same as callbacks/outages.py and
    # callbacks/reconductoring.py's editable tables - Dash components should
    # get plain JSON-serializable values (ISO date/datetime strings), not
    # raw date/datetime objects.
    reconductoring_rows = [event.model_dump(mode="json") for event in summary.reconductoring_events]
    outage_rows = [outage.model_dump(mode="json") for outage in summary.outages]

    reconductoring_table = _event_table(
        ["Date", "Conductor & treatment", "Grease", "Notes"],
        [
            [
                row["reconductoring_date"],
                row["conductor_and_treatment"] or "",
                row["grease"] or "",
                row["notes"] or "",
            ]
            for row in reconductoring_rows
        ],
        "No reconductoring events recorded for this site",
    )
    outage_table = _event_table(
        ["Start", "End", "Type", "Notes"],
        [
            [row["start_datetime"], row["end_datetime"], row["outage_type"], row["notes"] or ""]
            for row in outage_rows
        ],
        "No outages recorded for this site",
    )

    if summary.availability_start and summary.availability_end:
        availability_text = f"{summary.availability_start} to {summary.availability_end}"
    else:
        availability_text = "No processed reading data available"

    return html.Div(
        [
            html.H5("Reconductoring events"),
            reconductoring_table,
            html.H5("Outages"),
            outage_table,
            html.H5("Data availability"),
            html.P(availability_text),
            html.H5("Detected events"),
            html.P(
                f"Original: {summary.detected_event_count_original}, "
                f"Updated 2026: {summary.detected_event_count_updated_2026}"
            ),
        ]
    )


def register_callbacks(dash_app, backend_url: str | None):
    client = BackendClient(backend_url) if backend_url else None

    @dash_app.callback(
        Output("locations-map", "figure"),
        Input("locations-init", "n_intervals"),
    )
    def populate_locations_map(_n_intervals):
        sites = client.get_site_details() if client else []
        located = [s for s in sites if s.latitude is not None and s.longitude is not None]

        if located:
            center = {
                "lat": sum(s.latitude for s in located) / len(located),
                "lon": sum(s.longitude for s in located) / len(located),
            }
        else:
            center = DEFAULT_CENTER

        figure = go.Figure(
            go.Scattermap(
                lat=[s.latitude for s in located],
                lon=[s.longitude for s in located],
                mode="markers",
                marker=dict(size=12, color="red"),
                customdata=[
                    {"name": s.site_name, "id": s.noise_site_id} for s in located
                ],
                hovertemplate="Site: %{customdata.name}<br>ID: %{customdata.id}<extra></extra>",
            )
        )
        figure.update_layout(
            map=dict(style="open-street-map", center=center, zoom=8),
            height=600,
            clickmode="event+select",
            title="Noise Monitoring Site Locations",
        )
        return figure

    @dash_app.callback(
        Output("selected-site-info", "children"),
        Input("locations-map", "clickData"),
    )
    def display_selected_site(click_data):
        if not click_data:
            return "Click on a site marker to view information"

        point = click_data["points"][0]
        custom = point.get("customdata", {})
        lines = [
            f"📍 Site Name: {custom.get('name', 'Unknown')}",
            f"🆔 Site ID: {custom.get('id', 'Unknown')}",
            f"🌍 Latitude: {point.get('lat')}",
            f"🌍 Longitude: {point.get('lon')}",
        ]
        return [item for line in lines for item in (line, html.Br())][:-1]

    @dash_app.callback(
        Output("site-activity-panel", "children"),
        Input("locations-map", "clickData"),
    )
    def display_site_activity(click_data):
        site_id = _site_id_from_click(click_data)
        if site_id is None:
            return "Click on a site marker to view its activity"
        if client is None:
            return "No activity data for this site"

        summary = client.get_site_summary(site_id)
        return _build_site_activity_panel(summary)
