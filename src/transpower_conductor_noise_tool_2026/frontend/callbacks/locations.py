import plotly.graph_objects as go
from dash import Input, Output, html

from ..client import BackendClient

DEFAULT_CENTER = {"lat": -41.0, "lon": 174.9}


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
