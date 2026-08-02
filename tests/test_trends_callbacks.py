from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import trends as trends_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import trends as trends_layout

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
        ],
    )

    figure = output_value(response, "trends-conductor-summary-chart", "figure")
    assert figure == {"data": [{"type": "box"}], "layout": {}}

    filters = fake_client.get_conductor_summary_chart.call_args[0][0]
    assert filters.metric == "tone_200hz"
    assert filters.detection_logic == "updated_2026"
    assert filters.measurement_duration_minutes == 1


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
        ],
    )

    filters = fake_client.get_conductor_summary_chart.call_args[0][0]
    assert filters.metric == "l90"
    assert filters.detection_logic == "original"
    assert filters.measurement_duration_minutes == 15


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
        ],
    )

    figure = output_value(response, "trends-conductor-summary-chart", "figure")
    assert figure == {"data": [], "layout": {}}
