from importlib import import_module
from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import tab_loading
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import trends as trends_layout

from .dash_callback_utils import dispatch_callback, output_value

CALLBACKS = "transpower_conductor_noise_tool_2026.frontend.callbacks"
LAYOUT = "transpower_conductor_noise_tool_2026.frontend.layout"


def _build_tab_loading_app():
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = dash.html.Div()
    tab_loading.register_callbacks(app)
    return app


def _build_tab_app(module_name, fake_client):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = dash.html.Div()
    module = import_module(f"{CALLBACKS}.{module_name}")
    with patch(f"{CALLBACKS}.{module_name}.BackendClient", return_value=fake_client):
        module.register_callbacks(app, "http://fake-backend")
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


# --- tab_loading: main tabs ---------------------------------------------


@pytest.mark.parametrize("tab_id,interval_id", tab_loading.MAIN_TAB_INIT_INTERVALS.items())
def test_main_tab_interval_enabled_when_its_tab_is_opened(tab_id, interval_id):
    response = dispatch_callback(
        _build_tab_loading_app(),
        outputs=[(interval_id, "disabled")],
        inputs=[("main-tabs", "active_tab", tab_id)],
    )

    assert output_value(response, interval_id, "disabled") is False


@pytest.mark.parametrize("interval_id", tab_loading.MAIN_TAB_INIT_INTERVALS.values())
def test_main_tab_interval_untouched_while_charts_tab_is_active(interval_id):
    response = dispatch_callback(
        _build_tab_loading_app(),
        outputs=[(interval_id, "disabled")],
        inputs=[("main-tabs", "active_tab", "charts")],
    )

    assert response.status_code == 204


# --- tab_loading: Trends sub-tabs ---------------------------------------


def _dispatch_trends(interval_id, active_tab, active_trends_tab):
    return dispatch_callback(
        _build_tab_loading_app(),
        outputs=[(interval_id, "disabled")],
        inputs=[
            ("main-tabs", "active_tab", active_tab),
            ("trends-tabs", "active_tab", active_trends_tab),
        ],
    )


@pytest.mark.parametrize(
    "trends_tab_id,interval_id", tab_loading.TRENDS_TAB_INIT_INTERVALS.items()
)
def test_trends_sub_tab_interval_enabled_when_trends_and_sub_tab_are_active(
    trends_tab_id, interval_id
):
    response = _dispatch_trends(interval_id, "trends", trends_tab_id)

    assert output_value(response, interval_id, "disabled") is False


def test_trends_sub_tab_interval_untouched_while_trends_tab_is_hidden():
    # The default sub-tab is "active" from page load, but the Trends tab itself isn't.
    response = _dispatch_trends(
        "trends-rain-rate-init", "charts", trends_layout.RAIN_RATE_VS_LEVEL_TAB_ID
    )

    assert response.status_code == 204


def test_trends_sub_tab_interval_untouched_while_another_sub_tab_is_active():
    response = _dispatch_trends(
        "trends-age-effects-init", "trends", trends_layout.RAIN_RATE_VS_LEVEL_TAB_ID
    )

    assert response.status_code == 204


# --- layouts: hidden tabs' init intervals start disabled ------------------


def _find_component(component, component_id):
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    for child in children if isinstance(children, (list, tuple)) else [children]:
        found = _find_component(child, component_id)
        if found is not None:
            return found
    return None


@pytest.mark.parametrize(
    "layout_module,interval_id",
    [
        ("sites", "sites-init"),
        ("outages", "outages-init"),
        ("reconductoring", "reconductoring-init"),
        ("historical", "historical-init"),
        ("locations", "locations-init"),
        ("weather", "weather-init"),
        ("trends", "trends-rain-rate-init"),
        ("trends", "trends-age-effects-init"),
        ("trends", "trends-conductor-summary-init"),
    ],
)
def test_hidden_tab_init_interval_starts_disabled(layout_module, interval_id):
    module = import_module(f"{LAYOUT}.{layout_module}")
    interval = _find_component(module.content(), interval_id)

    assert interval is not None
    assert interval.disabled is True
    assert interval.max_intervals == 1


# --- init callbacks skip Dash's initial render (n_intervals=0) ------------


@pytest.mark.parametrize(
    "module_name,outputs,inputs,client_method",
    [
        (
            "outages",
            [("outages-table", "data"), ("outages-loaded-ids", "data")],
            [("outages-init", "n_intervals", 0)],
            "get_outages",
        ),
        (
            "sites",
            [("sites-table", "data")],
            [("sites-init", "n_intervals", 0), ("sites-status", "children", "")],
            "get_site_details",
        ),
        (
            "locations",
            [("locations-map", "figure")],
            [("locations-init", "n_intervals", 0)],
            "get_site_details",
        ),
        (
            "charts",
            [("chart-site-select", "options"), ("chart-site-select", "value")],
            [("chart-init", "n_intervals", 0)],
            "get_sites",
        ),
        (
            "trends",
            [("trends-age-effects-chart", "figure")],
            [
                ("trends-age-effects-init", "n_intervals", 0),
                ("trends-age-effects-detection-logic", "value", "original"),
                ("trends-age-effects-metric", "value", "l90"),
                ("trends-age-effects-site-select", "value", []),
                ("trends-age-effects-hide-data-button", "n_clicks", None),
            ],
            "get_age_effects_chart",
        ),
    ],
)
def test_init_callback_makes_no_backend_call_before_interval_fires(
    fake_client, module_name, outputs, inputs, client_method
):
    app = _build_tab_app(module_name, fake_client)

    response = dispatch_callback(app, outputs=outputs, inputs=inputs)

    assert response.status_code == 204
    getattr(fake_client, client_method).assert_not_called()
