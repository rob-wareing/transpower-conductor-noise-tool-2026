from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import weather as weather_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import weather as weather_layout
from transpower_conductor_noise_tool_2026.shared.contracts import (
    MonthlyRainfall,
    MonthlyWeatherStats,
    SiteSummary,
    WindRoseSector,
)

from .dash_callback_utils import dispatch_callback, output_value

NO_DATE_INPUTS = [
    ("weather-start-month", "value", None),
    ("weather-start-year", "value", None),
    ("weather-end-month", "value", None),
    ("weather-end-year", "value", None),
]


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
        inputs=[("weather-site-select", "value", None), *NO_DATE_INPUTS],
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
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    fake_client.get_wind_rose.assert_called_once_with(51, start=None, end=None)
    figure = output_value(response, "weather-wind-rose", "figure")
    assert figure["data"][0]["type"] == "barpolar"


def test_update_weather_wind_rose_passes_date_range_to_client(fake_client):
    fake_client.get_wind_rose.return_value = []
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[
            ("weather-site-select", "value", 51),
            ("weather-start-month", "value", 1),
            ("weather-start-year", "value", 2025),
            ("weather-end-month", "value", 6),
            ("weather-end-year", "value", 2026),
        ],
    )

    fake_client.get_wind_rose.assert_called_once_with(51, start="2025-01", end="2026-06")


def test_update_weather_wind_rose_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_wind_rose.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    assert output_value(response, "weather-wind-rose", "figure")["data"] == []


def test_update_weather_wind_rose_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("weather-wind-rose", "figure")],
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    assert output_value(response, "weather-wind-rose", "figure")["data"] == []


# --- update_weather_monthly_rainfall ----------------------------------------


def test_update_weather_monthly_rainfall_shows_placeholder_when_no_site_selected(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", None), *NO_DATE_INPUTS],
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
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    fake_client.get_monthly_rainfall.assert_called_once_with(51, start=None, end=None)
    figure = output_value(response, "weather-monthly-rainfall", "figure")
    assert figure["data"][0]["type"] == "bar"
    assert figure["data"][0]["y"][0] == 35.0  # Jan


def test_update_weather_monthly_rainfall_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_monthly_rainfall.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    assert output_value(response, "weather-monthly-rainfall", "figure")["data"] == []


def test_update_weather_monthly_rainfall_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("weather-monthly-rainfall", "figure")],
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    assert output_value(response, "weather-monthly-rainfall", "figure")["data"] == []


# --- update_weather_range_stats ----------------------------------------------


def test_update_weather_range_stats_shows_placeholder_when_no_site_selected(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-rainfall-stats", "figure"), ("weather-windspeed-stats", "figure")],
        inputs=[("weather-site-select", "value", None), *NO_DATE_INPUTS],
    )

    assert output_value(response, "weather-rainfall-stats", "figure")["data"] == []
    assert output_value(response, "weather-windspeed-stats", "figure")["data"] == []


def test_update_weather_range_stats_shows_placeholder_when_no_range_selected(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-rainfall-stats", "figure"), ("weather-windspeed-stats", "figure")],
        inputs=[("weather-site-select", "value", 51), *NO_DATE_INPUTS],
    )

    fake_client.get_monthly_weather_stats.assert_not_called()
    assert output_value(response, "weather-rainfall-stats", "figure")["data"] == []


def test_update_weather_range_stats_builds_both_charts_from_backend_data(fake_client):
    fake_client.get_monthly_weather_stats.return_value = [
        MonthlyWeatherStats(
            year=2026,
            month=1,
            min_rain_mm=1.0,
            max_rain_mm=5.0,
            avg_rain_mm=3.0,
            min_wind_speed=2.0,
            max_wind_speed=8.0,
            avg_wind_speed=5.0,
            sample_count=100,
        ),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-rainfall-stats", "figure"), ("weather-windspeed-stats", "figure")],
        inputs=[
            ("weather-site-select", "value", 51),
            ("weather-start-month", "value", 1),
            ("weather-start-year", "value", 2026),
            ("weather-end-month", "value", 6),
            ("weather-end-year", "value", 2026),
        ],
    )

    fake_client.get_monthly_weather_stats.assert_called_once_with(
        51, start="2026-01", end="2026-06"
    )
    rainfall_figure = output_value(response, "weather-rainfall-stats", "figure")
    windspeed_figure = output_value(response, "weather-windspeed-stats", "figure")
    assert rainfall_figure["data"][2]["y"] == [3.0]  # mean trace
    assert windspeed_figure["data"][2]["y"] == [5.0]  # mean trace


def test_update_weather_range_stats_shows_empty_state_when_backend_has_no_data(fake_client):
    fake_client.get_monthly_weather_stats.return_value = []
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("weather-rainfall-stats", "figure"), ("weather-windspeed-stats", "figure")],
        inputs=[
            ("weather-site-select", "value", 51),
            ("weather-start-month", "value", 1),
            ("weather-start-year", "value", 2026),
            *NO_DATE_INPUTS[2:],
        ],
    )

    assert output_value(response, "weather-rainfall-stats", "figure")["data"] == []


def test_update_weather_range_stats_handles_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("weather-rainfall-stats", "figure"), ("weather-windspeed-stats", "figure")],
        inputs=[
            ("weather-site-select", "value", 51),
            ("weather-start-month", "value", 1),
            ("weather-start-year", "value", 2026),
            *NO_DATE_INPUTS[2:],
        ],
    )

    assert output_value(response, "weather-rainfall-stats", "figure")["data"] == []
