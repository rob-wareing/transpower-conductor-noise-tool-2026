from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import trends as trends_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import trends as trends_layout
from transpower_conductor_noise_tool_2026.shared.contracts import SiteSummary

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = trends_layout.content()
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.trends.BackendClient",
            return_value=fake_client,
        ):
            trends_callbacks.register_callbacks(app, backend_url)
    else:
        trends_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


# --- populate_rain_rate_site_options ---------------------------------------


def test_populate_rain_rate_site_options_formats_label_from_client(fake_client):
    fake_client.get_sites.return_value = [
        SiteSummary(noise_site_id=51, site_name="Demo Site", site_code="DS"),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("trends-rain-rate-site-select", "options")],
        inputs=[("trends-rain-rate-init", "n_intervals", 1)],
    )

    options = output_value(response, "trends-rain-rate-site-select", "options")
    assert options == [{"label": "(51) Demo Site", "value": 51}]


def test_populate_rain_rate_site_options_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("trends-rain-rate-site-select", "options")],
        inputs=[("trends-rain-rate-init", "n_intervals", 1)],
    )

    assert output_value(response, "trends-rain-rate-site-select", "options") == []


# --- refresh_rain_rate_chart -------------------------------------------------


def test_refresh_rain_rate_chart_passes_selected_filters(fake_client):
    fake_client.get_rain_rate_vs_level_chart.return_value = {
        "data": [{"type": "scatter"}],
        "layout": {},
    }
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("trends-rain-rate-chart", "figure")],
        inputs=[
            ("trends-rain-rate-init", "n_intervals", 1),
            ("trends-rain-rate-detection-logic", "value", "updated_2026"),
            ("trends-rain-rate-metric", "value", "tone_200hz"),
            ("trends-rain-rate-site-select", "value", [51, 137]),
            ("trends-rain-rate-include-dry", "value", True),
        ],
    )

    figure = output_value(response, "trends-rain-rate-chart", "figure")
    assert figure == {"data": [{"type": "scatter"}], "layout": {}}

    filters = fake_client.get_rain_rate_vs_level_chart.call_args[0][0]
    assert filters.detection_logic == "updated_2026"
    assert filters.metric == "tone_200hz"
    assert filters.noise_site_id == [51, 137]
    assert filters.include_dry is True


def test_refresh_rain_rate_chart_defaults_when_dropdowns_empty(fake_client):
    fake_client.get_rain_rate_vs_level_chart.return_value = {"data": [], "layout": {}}
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("trends-rain-rate-chart", "figure")],
        inputs=[
            ("trends-rain-rate-init", "n_intervals", 1),
            ("trends-rain-rate-detection-logic", "value", None),
            ("trends-rain-rate-metric", "value", None),
            ("trends-rain-rate-site-select", "value", None),
            ("trends-rain-rate-include-dry", "value", None),
        ],
    )

    filters = fake_client.get_rain_rate_vs_level_chart.call_args[0][0]
    assert filters.detection_logic == "original"
    assert filters.metric == "l90"
    assert filters.noise_site_id == []
    assert filters.include_dry is False


def test_refresh_rain_rate_chart_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("trends-rain-rate-chart", "figure")],
        inputs=[
            ("trends-rain-rate-init", "n_intervals", 1),
            ("trends-rain-rate-detection-logic", "value", "original"),
            ("trends-rain-rate-metric", "value", "l90"),
            ("trends-rain-rate-site-select", "value", []),
            ("trends-rain-rate-include-dry", "value", False),
        ],
    )

    figure = output_value(response, "trends-rain-rate-chart", "figure")
    assert figure == {"data": [], "layout": {}}


# --- populate_conductor_summary_site_options --------------------------------


def test_populate_conductor_summary_site_options_formats_label_from_client(fake_client):
    fake_client.get_sites.return_value = [
        SiteSummary(noise_site_id=51, site_name="Demo Site", site_code="DS"),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("trends-conductor-summary-site-select", "options")],
        inputs=[("trends-conductor-summary-init", "n_intervals", 1)],
    )

    options = output_value(response, "trends-conductor-summary-site-select", "options")
    assert options == [{"label": "(51) Demo Site", "value": 51}]


def test_populate_conductor_summary_site_options_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("trends-conductor-summary-site-select", "options")],
        inputs=[("trends-conductor-summary-init", "n_intervals", 1)],
    )

    assert output_value(response, "trends-conductor-summary-site-select", "options") == []


# --- refresh_conductor_summary_chart ----------------------------------------


def test_refresh_conductor_summary_chart_passes_selected_filters(fake_client):
    fake_client.get_conductor_summary_chart.return_value = {"data": [{"type": "box"}], "layout": {}}
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("trends-conductor-summary-chart", "figure")],
        inputs=[
            ("trends-conductor-summary-init", "n_intervals", 1),
            ("trends-conductor-summary-metric", "value", "tone_200hz"),
            ("trends-conductor-summary-detection-logic", "value", "updated_2026"),
            ("trends-conductor-summary-duration", "value", 1),
            ("trends-conductor-summary-site-select", "value", [51, 137]),
        ],
    )

    figure = output_value(response, "trends-conductor-summary-chart", "figure")
    assert figure == {"data": [{"type": "box"}], "layout": {}}

    filters = fake_client.get_conductor_summary_chart.call_args[0][0]
    assert filters.metric == "tone_200hz"
    assert filters.detection_logic == "updated_2026"
    assert filters.measurement_duration_minutes == 1
    assert filters.noise_site_id == [51, 137]


def test_refresh_conductor_summary_chart_defaults_when_dropdowns_empty(fake_client):
    fake_client.get_conductor_summary_chart.return_value = {"data": [], "layout": {}}
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("trends-conductor-summary-chart", "figure")],
        inputs=[
            ("trends-conductor-summary-init", "n_intervals", 1),
            ("trends-conductor-summary-metric", "value", None),
            ("trends-conductor-summary-detection-logic", "value", None),
            ("trends-conductor-summary-duration", "value", None),
            ("trends-conductor-summary-site-select", "value", None),
        ],
    )

    filters = fake_client.get_conductor_summary_chart.call_args[0][0]
    assert filters.metric == "l90"
    assert filters.detection_logic == "original"
    assert filters.measurement_duration_minutes == 15
    assert filters.noise_site_id == []


def test_refresh_conductor_summary_chart_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("trends-conductor-summary-chart", "figure")],
        inputs=[
            ("trends-conductor-summary-init", "n_intervals", 1),
            ("trends-conductor-summary-metric", "value", "l90"),
            ("trends-conductor-summary-detection-logic", "value", "original"),
            ("trends-conductor-summary-duration", "value", 15),
            ("trends-conductor-summary-site-select", "value", []),
        ],
    )

    figure = output_value(response, "trends-conductor-summary-chart", "figure")
    assert figure == {"data": [], "layout": {}}


# --- populate_age_effects_site_options --------------------------------------


def test_populate_age_effects_site_options_formats_label_from_client(fake_client):
    fake_client.get_sites.return_value = [
        SiteSummary(noise_site_id=51, site_name="Demo Site", site_code="DS"),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("trends-age-effects-site-select", "options")],
        inputs=[("trends-age-effects-init", "n_intervals", 1)],
    )

    options = output_value(response, "trends-age-effects-site-select", "options")
    assert options == [{"label": "(51) Demo Site", "value": 51}]


def test_populate_age_effects_site_options_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("trends-age-effects-site-select", "options")],
        inputs=[("trends-age-effects-init", "n_intervals", 1)],
    )

    assert output_value(response, "trends-age-effects-site-select", "options") == []


# --- refresh_age_effects_chart -----------------------------------------------


def test_refresh_age_effects_chart_passes_selected_filters(fake_client):
    fake_client.get_age_effects_chart.return_value = {
        "data": [{"type": "scatter"}],
        "layout": {},
    }
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("trends-age-effects-chart", "figure")],
        inputs=[
            ("trends-age-effects-init", "n_intervals", 1),
            ("trends-age-effects-detection-logic", "value", "updated_2026"),
            ("trends-age-effects-metric", "value", "tone_200hz"),
            ("trends-age-effects-site-select", "value", [51, 137]),
        ],
    )

    figure = output_value(response, "trends-age-effects-chart", "figure")
    assert figure == {"data": [{"type": "scatter"}], "layout": {}}

    filters = fake_client.get_age_effects_chart.call_args[0][0]
    assert filters.detection_logic == "updated_2026"
    assert filters.metric == "tone_200hz"
    assert filters.noise_site_id == [51, 137]


def test_refresh_age_effects_chart_defaults_when_dropdowns_empty(fake_client):
    fake_client.get_age_effects_chart.return_value = {"data": [], "layout": {}}
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("trends-age-effects-chart", "figure")],
        inputs=[
            ("trends-age-effects-init", "n_intervals", 1),
            ("trends-age-effects-detection-logic", "value", None),
            ("trends-age-effects-metric", "value", None),
            ("trends-age-effects-site-select", "value", None),
        ],
    )

    filters = fake_client.get_age_effects_chart.call_args[0][0]
    assert filters.detection_logic == "original"
    assert filters.metric == "l90"
    assert filters.noise_site_id == []


def test_refresh_age_effects_chart_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("trends-age-effects-chart", "figure")],
        inputs=[
            ("trends-age-effects-init", "n_intervals", 1),
            ("trends-age-effects-detection-logic", "value", "original"),
            ("trends-age-effects-metric", "value", "l90"),
            ("trends-age-effects-site-select", "value", []),
        ],
    )

    figure = output_value(response, "trends-age-effects-chart", "figure")
    assert figure == {"data": [], "layout": {}}
