from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import locations as locations_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import locations as locations_layout
from transpower_conductor_noise_tool_2026.shared.contracts import (
    MonthlyRainfall,
    SiteDetail,
    WindRoseSector,
)

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = locations_layout.content()
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.locations.BackendClient",
            return_value=fake_client,
        ):
            locations_callbacks.register_callbacks(app, backend_url)
    else:
        locations_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


def _site(**overrides):
    fields = {"noise_site_id": 51, "site_name": "Demo Site", "latitude": None, "longitude": None}
    fields.update(overrides)
    return SiteDetail(**fields)


# --- populate_locations_map -----------------------------------------------


def test_populate_locations_map_excludes_sites_missing_either_coordinate(fake_client):
    fake_client.get_site_details.return_value = [
        _site(noise_site_id=51, latitude=-41.0, longitude=174.9),
        _site(noise_site_id=52, latitude=-40.0, longitude=None),
        _site(noise_site_id=53, latitude=None, longitude=175.0),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-map", "figure")],
        inputs=[("locations-init", "n_intervals", 1)],
    )

    figure = output_value(response, "locations-map", "figure")
    trace = figure["data"][0]
    assert trace["lat"] == [-41.0]
    assert trace["lon"] == [174.9]
    assert trace["customdata"] == [{"name": "Demo Site", "id": 51}]


def test_populate_locations_map_centers_on_mean_of_located_sites(fake_client):
    fake_client.get_site_details.return_value = [
        _site(noise_site_id=51, latitude=-40.0, longitude=170.0),
        _site(noise_site_id=52, latitude=-42.0, longitude=180.0),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-map", "figure")],
        inputs=[("locations-init", "n_intervals", 1)],
    )

    figure = output_value(response, "locations-map", "figure")
    center = figure["layout"]["mapbox"]["center"]
    assert center == {"lat": -41.0, "lon": 175.0}


def test_populate_locations_map_falls_back_to_default_center_when_no_sites_located(fake_client):
    fake_client.get_site_details.return_value = [_site(latitude=None, longitude=None)]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-map", "figure")],
        inputs=[("locations-init", "n_intervals", 1)],
    )

    figure = output_value(response, "locations-map", "figure")
    assert figure["data"][0]["lat"] == []
    assert figure["layout"]["mapbox"]["center"] == locations_callbacks.DEFAULT_CENTER


def test_populate_locations_map_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("locations-map", "figure")],
        inputs=[("locations-init", "n_intervals", 1)],
    )

    figure = output_value(response, "locations-map", "figure")
    assert figure["data"][0]["lat"] == []
    assert figure["layout"]["mapbox"]["center"] == locations_callbacks.DEFAULT_CENTER


# --- display_selected_site -------------------------------------------------


def test_display_selected_site_shows_placeholder_when_nothing_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("selected-site-info", "children")],
        inputs=[("locations-map", "clickData", None)],
    )

    assert output_value(response, "selected-site-info", "children") == (
        "Click on a site marker to view information"
    )


def test_display_selected_site_extracts_info_from_click_payload(fake_client):
    app = _build_app(fake_client)

    click_data = {
        "points": [
            {
                "customdata": {"name": "Demo Site", "id": 51},
                "lat": -41.0,
                "lon": 174.9,
            }
        ]
    }
    response = dispatch_callback(
        app,
        outputs=[("selected-site-info", "children")],
        inputs=[("locations-map", "clickData", click_data)],
    )

    lines = output_value(response, "selected-site-info", "children")
    # html.Br() interleaving: text, <br>, text, <br>, ... with the trailing
    # <br> trimmed - four text lines means seven entries, not eight.
    assert len(lines) == 7
    text_lines = [entry for entry in lines if isinstance(entry, str)]
    assert any("Demo Site" in line for line in text_lines)
    assert any("51" in line for line in text_lines)
    assert any("-41.0" in line for line in text_lines)
    assert any("174.9" in line for line in text_lines)


# --- update_wind_rose --------------------------------------------------


CLICK_DATA = {"points": [{"customdata": {"name": "Demo Site", "id": 51}}]}


def test_update_wind_rose_shows_placeholder_when_nothing_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-wind-rose", "figure")],
        inputs=[("locations-map", "clickData", None)],
    )

    figure = output_value(response, "locations-wind-rose", "figure")
    assert figure["data"] == []


def test_update_wind_rose_builds_barpolar_from_backend_data(fake_client):
    fake_client.get_wind_rose.return_value = [
        WindRoseSector(direction_sector="N", sample_count=10, avg_wind_speed=4.5),
        WindRoseSector(direction_sector="S", sample_count=3, avg_wind_speed=2.0),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-wind-rose", "figure")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    fake_client.get_wind_rose.assert_called_once_with(51)
    figure = output_value(response, "locations-wind-rose", "figure")
    trace = figure["data"][0]
    assert trace["type"] == "barpolar"
    assert trace["theta"] == locations_callbacks.DIRECTION_SECTORS
    # zero-filled for every sector not returned by the backend
    n_index = locations_callbacks.DIRECTION_SECTORS.index("N")
    s_index = locations_callbacks.DIRECTION_SECTORS.index("S")
    assert trace["r"][n_index] == 10
    assert trace["r"][s_index] == 3
    other_indexes = set(range(16)) - {n_index, s_index}
    assert all(trace["r"][i] == 0 for i in other_indexes)


def test_update_wind_rose_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_wind_rose.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-wind-rose", "figure")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    figure = output_value(response, "locations-wind-rose", "figure")
    assert figure["data"] == []


def test_update_wind_rose_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("locations-wind-rose", "figure")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    figure = output_value(response, "locations-wind-rose", "figure")
    assert figure["data"] == []


# --- update_monthly_rainfall ---------------------------------------------


def test_update_monthly_rainfall_shows_placeholder_when_nothing_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-monthly-rainfall", "figure")],
        inputs=[("locations-map", "clickData", None)],
    )

    figure = output_value(response, "locations-monthly-rainfall", "figure")
    assert figure["data"] == []


def test_update_monthly_rainfall_builds_bar_chart_from_backend_data(fake_client):
    fake_client.get_monthly_rainfall.return_value = [
        MonthlyRainfall(month=1, avg_rain_mm=3.5, sample_count=20),
        MonthlyRainfall(month=6, avg_rain_mm=8.0, sample_count=15),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-monthly-rainfall", "figure")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    fake_client.get_monthly_rainfall.assert_called_once_with(51)
    figure = output_value(response, "locations-monthly-rainfall", "figure")
    trace = figure["data"][0]
    assert trace["type"] == "bar"
    assert trace["x"] == locations_callbacks.MONTH_LABELS
    assert trace["y"][0] == 3.5  # Jan
    assert trace["y"][5] == 8.0  # Jun
    assert trace["y"][1] == 0  # Feb, zero-filled


def test_update_monthly_rainfall_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_monthly_rainfall.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("locations-monthly-rainfall", "figure")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    figure = output_value(response, "locations-monthly-rainfall", "figure")
    assert figure["data"] == []
