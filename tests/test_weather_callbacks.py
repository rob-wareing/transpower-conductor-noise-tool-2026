from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import weather as weather_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import weather as weather_layout
from transpower_conductor_noise_tool_2026.shared.contracts import (
    MonthlyRainfall,
    SiteSummary,
    WindRoseSector,
)

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = weather_layout.content()
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.weather.BackendClient",
            return_value=fake_client,
        ):
            weather_callbacks.register_callbacks(app, backend_url)
    else:
        weather_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


# --- populate_weather_site_options -----------------------------------------


def test_populate_weather_site_options_formats_label_from_client(fake_client):
    fake_client.get_sites.return_value = [
        SiteSummary(noise_site_id=51, site_name="Demo Site", site_code="DS"),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-site-select", "options")],
        inputs=[("weather-init", "n_intervals", 1)],
    )

    assert output_value(response, "weather-site-select", "options") == [
        {"label": "(51) Demo Site", "value": 51}
    ]


def test_populate_weather_site_options_returns_empty_when_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("weather-site-select", "options")],
        inputs=[("weather-init", "n_intervals", 1)],
    )

    assert output_value(response, "weather-site-select", "options") == []


# --- update_weather_wind_rose -----------------------------------------------


def test_update_weather_wind_rose_shows_placeholder_when_no_site_selected(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[("weather-site-select", "value", None)],
    )

    assert output_value(response, "weather-wind-rose", "figure")["data"] == []


def test_update_weather_wind_rose_builds_barpolar_from_backend_data(fake_client):
    fake_client.get_wind_rose.return_value = [
        WindRoseSector(direction_sector="N", sample_count=10, avg_wind_speed=4.5),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[("weather-site-select", "value", 51)],
    )

    fake_client.get_wind_rose.assert_called_once_with(51)
    figure = output_value(response, "weather-wind-rose", "figure")
    assert figure["data"][0]["type"] == "barpolar"


def test_update_weather_wind_rose_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_wind_rose.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[("weather-site-select", "value", 51)],
    )

    assert output_value(response, "weather-wind-rose", "figure")["data"] == []


def test_update_weather_wind_rose_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[("weather-site-select", "value", 51)],
    )

    assert output_value(response, "weather-wind-rose", "figure")["data"] == []


# --- update_weather_monthly_rainfall ----------------------------------------


def test_update_weather_monthly_rainfall_shows_placeholder_when_no_site_selected(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", None)],
    )

    assert output_value(response, "weather-monthly-rainfall", "figure")["data"] == []


def test_update_weather_monthly_rainfall_builds_bar_chart_from_backend_data(fake_client):
    fake_client.get_monthly_rainfall.return_value = [
        MonthlyRainfall(month=1, avg_rain_mm=3.5, total_rain=35.0, sample_count=20),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", 51)],
    )

    fake_client.get_monthly_rainfall.assert_called_once_with(51)
    figure = output_value(response, "weather-monthly-rainfall", "figure")
    assert figure["data"][0]["type"] == "bar"
    assert figure["data"][0]["y"][0] == 35.0  # Jan


def test_update_weather_monthly_rainfall_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_monthly_rainfall.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", 51)],
    )

    assert output_value(response, "weather-monthly-rainfall", "figure")["data"] == []


def test_update_weather_monthly_rainfall_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", 51)],
    )

    assert output_value(response, "weather-monthly-rainfall", "figure")["data"] == []
