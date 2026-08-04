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
            marker=dict(color=speeds, colorscale="Viridis", colorbar=dict(title="Avg speed")),
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
    by_month = {row.month: row for row in months}
    values = [by_month[m].avg_rain_mm if m in by_month else 0 for m in range(1, 13)]

    figure = go.Figure(go.Bar(x=MONTH_LABELS, y=values))
    figure.update_layout(
        title="Average Monthly Rainfall",
        yaxis_title="Rain (mm)",
        height=400,
    )
    return figure


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
            go.Scattermapbox(
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
            mapbox=dict(style="open-street-map", center=center, zoom=8),
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
        Output("locations-wind-rose", "figure"),
        Input("locations-map", "clickData"),
    )
    def update_wind_rose(click_data):
        site_id = _site_id_from_click(click_data)
        if site_id is None:
            return _empty_figure("Click a site to view its wind rose")
        if client is None:
            return _empty_figure("No wind data for this site")

        sectors = client.get_wind_rose(site_id)
        if not sectors:
            return _empty_figure("No wind data for this site")
        return _build_wind_rose_figure(sectors)

    @dash_app.callback(
        Output("locations-monthly-rainfall", "figure"),
        Input("locations-map", "clickData"),
    )
    def update_monthly_rainfall(click_data):
        site_id = _site_id_from_click(click_data)
        if site_id is None:
            return _empty_figure("Click a site to view its monthly rainfall")
        if client is None:
            return _empty_figure("No rainfall data for this site")

        months = client.get_monthly_rainfall(site_id)
        if not months:
            return _empty_figure("No rainfall data for this site")
        return _build_monthly_rainfall_figure(months)
