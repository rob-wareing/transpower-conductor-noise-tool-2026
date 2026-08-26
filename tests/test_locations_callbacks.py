from datetime import date, datetime
from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import locations as locations_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import locations as locations_layout
from transpower_conductor_noise_tool_2026.shared.contracts import (
    OutageDetail,
    ReconductoringDetail,
    SiteActivitySummary,
    SiteDetail,
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


# --- display_site_activity --------------------------------------------


CLICK_DATA = {"points": [{"customdata": {"name": "Demo Site", "id": 51}}]}


def test_display_site_activity_shows_placeholder_when_nothing_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("site-activity-panel", "children")],
        inputs=[("locations-map", "clickData", None)],
    )

    assert output_value(response, "site-activity-panel", "children") == (
        "Click on a site marker to view its activity"
    )


def test_display_site_activity_renders_summary_from_backend_data(fake_client):
    fake_client.get_site_summary.return_value = SiteActivitySummary(
        reconductoring_events=[
            ReconductoringDetail(
                id=1,
                noise_site_id=51,
                conductor_and_treatment="ACSR",
                grease=None,
                reconductoring_date=date(2024, 3, 1),
                notes=None,
            )
        ],
        outages=[
            OutageDetail(
                id=1,
                noise_site_id=51,
                outage_type="planned",
                start_datetime=datetime(2024, 1, 1),
                end_datetime=datetime(2024, 1, 2),
                notes=None,
            )
        ],
        availability_start=datetime(2020, 1, 1),
        availability_end=datetime(2026, 1, 1),
        detected_event_count_original=10,
        detected_event_count_updated_2026=8,
    )
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("site-activity-panel", "children")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    fake_client.get_site_summary.assert_called_once_with(51)
    children = output_value(response, "site-activity-panel", "children")
    rendered = str(children)
    assert "ACSR" in rendered
    assert "planned" in rendered
    assert "2020-01-01" in rendered
    assert "10" in rendered
    assert "8" in rendered


def test_display_site_activity_shows_empty_messages_when_no_history(fake_client):
    fake_client.get_site_summary.return_value = SiteActivitySummary(
        reconductoring_events=[],
        outages=[],
        availability_start=None,
        availability_end=None,
        detected_event_count_original=0,
        detected_event_count_updated_2026=0,
    )
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("site-activity-panel", "children")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    rendered = str(output_value(response, "site-activity-panel", "children"))
    assert "No reconductoring events recorded" in rendered
    assert "No outages recorded" in rendered
    assert "No processed reading data available" in rendered


def test_display_site_activity_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("site-activity-panel", "children")],
        inputs=[("locations-map", "clickData", CLICK_DATA)],
    )

    assert output_value(response, "site-activity-panel", "children") == (
        "No activity data for this site"
    )
