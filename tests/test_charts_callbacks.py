from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import charts as charts_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import charts as charts_layout
from transpower_conductor_noise_tool_2026.shared.contracts import (
    ChartTableRow,
    ReconductoringDetail,
    SiteSummary,
)

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = charts_layout.content(write_access=True)
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.charts.BackendClient",
            return_value=fake_client,
        ):
            charts_callbacks.register_callbacks(app, backend_url)
    else:
        charts_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


# --- populate_site_options ---------------------------------------------


def test_populate_site_options_formats_label_from_client(fake_client):
    fake_client.get_sites.return_value = [
        SiteSummary(noise_site_id=51, site_name="Demo Site", site_code="DS"),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-site-select", "options")],
        inputs=[("chart-init", "n_intervals", 1)],
    )

    assert output_value(response, "chart-site-select", "options") == [
        {"label": "(51) Demo Site", "value": 51}
    ]


def test_populate_site_options_returns_empty_when_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("chart-site-select", "options")],
        inputs=[("chart-init", "n_intervals", 1)],
    )

    assert output_value(response, "chart-site-select", "options") == []


# --- populate_conductor_treatment_options / populate_grease_options ----


def _events():
    return [
        ReconductoringDetail(
            id=1,
            noise_site_id=51,
            conductor_and_treatment="Standard conductor (standard grease)",
            grease="standard",
            reconductoring_date="2024-11-15",
        ),
        ReconductoringDetail(
            id=2,
            noise_site_id=52,
            conductor_and_treatment="High-temp conductor (synthetic grease)",
            grease="synthetic",
            reconductoring_date="2024-02-01",
        ),
        # Same conductor/grease as event 1 but a different site+date - exercises dedupe.
        ReconductoringDetail(
            id=3,
            noise_site_id=51,
            conductor_and_treatment="Standard conductor (standard grease)",
            grease="standard",
            reconductoring_date="2025-01-01",
        ),
    ]


def test_populate_conductor_treatment_options_unfiltered_and_sorted(fake_client):
    fake_client.get_reconductoring_events.return_value = _events()
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[
            ("chart-conductor-treatment", "options"),
            ("chart-conductor-treatment", "value"),
        ],
        inputs=[("chart-site-select", "value", None)],
        state=[("chart-conductor-treatment", "value", [])],
    )

    options = output_value(response, "chart-conductor-treatment", "options")
    assert options == [
        {"label": "High-temp conductor (synthetic grease)", "value": "High-temp conductor (synthetic grease)"},
        {"label": "Standard conductor (standard grease)", "value": "Standard conductor (standard grease)"},
    ]


def test_populate_conductor_treatment_options_filters_by_selected_sites(fake_client):
    fake_client.get_reconductoring_events.return_value = _events()
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[
            ("chart-conductor-treatment", "options"),
            ("chart-conductor-treatment", "value"),
        ],
        inputs=[("chart-site-select", "value", [51])],
        state=[("chart-conductor-treatment", "value", [])],
    )

    options = output_value(response, "chart-conductor-treatment", "options")
    assert options == [
        {
            "label": "Standard conductor (standard grease)",
            "value": "Standard conductor (standard grease)",
        }
    ]


def test_populate_conductor_treatment_options_drops_stale_selected_value(fake_client):
    # Site 51 is selected, so only "Standard conductor..." is a valid option
    # any more - a previously-selected "High-temp conductor..." value (only
    # valid for site 52) must be dropped rather than left dangling.
    fake_client.get_reconductoring_events.return_value = _events()
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[
            ("chart-conductor-treatment", "options"),
            ("chart-conductor-treatment", "value"),
        ],
        inputs=[("chart-site-select", "value", [51])],
        state=[
            (
                "chart-conductor-treatment",
                "value",
                ["Standard conductor (standard grease)", "High-temp conductor (synthetic grease)"],
            )
        ],
    )

    assert output_value(response, "chart-conductor-treatment", "value") == [
        "Standard conductor (standard grease)"
    ]


def test_populate_grease_options_uses_grease_field(fake_client):
    fake_client.get_reconductoring_events.return_value = _events()
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-grease", "options"), ("chart-grease", "value")],
        inputs=[("chart-site-select", "value", [52])],
        state=[("chart-grease", "value", [])],
    )

    assert output_value(response, "chart-grease", "options") == [
        {"label": "synthetic", "value": "synthetic"}
    ]


# --- refresh_charts ------------------------------------------------------


def _chart_inputs(**overrides):
    values = {
        "chart-init.n_intervals": 1,
        "chart-site-select.value": None,
        "chart-date-range.start_date": None,
        "chart-date-range.end_date": None,
        "chart-condition.value": None,
        "chart-parameter.value": None,
        "chart-interval-weeks.value": None,
        "chart-conductor-treatment.value": None,
        "chart-grease.value": None,
        "chart-plot-by.value": None,
        "chart-measurement-duration.value": None,
        "chart-detection-logic.value": None,
        "chart-show-historical.value": None,
    }
    values.update(overrides)
    return [(key.split(".")[0], key.split(".")[1], value) for key, value in values.items()]


def test_refresh_charts_fills_in_defaults_for_falsy_inputs(fake_client):
    fake_client.get_charts.return_value = {
        "noise_chart": {"data": [], "layout": {"title": "noise"}},
        "timeline_chart": {"data": [], "layout": {"title": "timeline"}},
    }
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("noise-chart", "figure"), ("timeline-chart", "figure")],
        inputs=_chart_inputs(),
    )

    assert output_value(response, "noise-chart", "figure") == {
        "data": [],
        "layout": {"title": "noise"},
    }
    assert output_value(response, "timeline-chart", "figure") == {
        "data": [],
        "layout": {"title": "timeline"},
    }

    filters = fake_client.get_charts.call_args[0][0]
    assert filters.noise_site_id == []
    assert filters.condition == "all"
    assert filters.parameter == "tone_100hz"
    assert filters.interval_weeks == 2
    assert filters.conductor_and_treatment == []
    assert filters.grease == []
    assert filters.plot_by == "datetime"
    assert filters.measurement_duration == 15
    assert filters.detection_logic == "original"
    assert filters.show_historical is False


def test_refresh_charts_passes_through_explicit_filter_values(fake_client):
    fake_client.get_charts.return_value = {
        "noise_chart": {"data": [], "layout": {}},
        "timeline_chart": {"data": [], "layout": {}},
    }
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("noise-chart", "figure"), ("timeline-chart", "figure")],
        inputs=_chart_inputs(**{
            "chart-site-select.value": [51],
            "chart-condition.value": "dry",
            "chart-parameter.value": "leq_adj",
            "chart-interval-weeks.value": 4,
            "chart-conductor-treatment.value": ["Standard conductor (standard grease)"],
            "chart-grease.value": ["standard"],
            "chart-plot-by.value": "days_since_conductoring",
            "chart-measurement-duration.value": "1min",
            "chart-detection-logic.value": "updated_2026",
            "chart-show-historical.value": True,
        }),
    )

    filters = fake_client.get_charts.call_args[0][0]
    assert filters.noise_site_id == [51]
    assert filters.condition == "dry"
    assert filters.parameter == "leq_adj"
    assert filters.interval_weeks == 4
    assert filters.conductor_and_treatment == ["Standard conductor (standard grease)"]
    assert filters.grease == ["standard"]
    assert filters.plot_by == "days_since_conductoring"
    assert filters.measurement_duration == 1
    assert filters.detection_logic == "updated_2026"
    assert filters.show_historical is True


def test_refresh_charts_returns_empty_figures_when_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("noise-chart", "figure"), ("timeline-chart", "figure")],
        inputs=_chart_inputs(),
    )

    empty_figure = {"data": [], "layout": {}}
    assert output_value(response, "noise-chart", "figure") == empty_figure
    assert output_value(response, "timeline-chart", "figure") == empty_figure


# --- toggle_chart_table ---------------------------------------------------


def test_toggle_chart_table_ignores_falsy_n_clicks_and_stays_closed(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table-collapse", "is_open")],
        inputs=[("chart-toggle-table-button", "n_clicks", 0)],
        state=[("chart-table-collapse", "is_open", True)],
    )

    assert output_value(response, "chart-table-collapse", "is_open") is False


def test_toggle_chart_table_flips_open_state_on_click(fake_client):
    app = _build_app(fake_client)

    opened = dispatch_callback(
        app,
        outputs=[("chart-table-collapse", "is_open")],
        inputs=[("chart-toggle-table-button", "n_clicks", 1)],
        state=[("chart-table-collapse", "is_open", False)],
    )
    assert output_value(opened, "chart-table-collapse", "is_open") is True

    closed = dispatch_callback(
        app,
        outputs=[("chart-table-collapse", "is_open")],
        inputs=[("chart-toggle-table-button", "n_clicks", 2)],
        state=[("chart-table-collapse", "is_open", True)],
    )
    assert output_value(closed, "chart-table-collapse", "is_open") is False


# --- refresh_chart_table ---------------------------------------------------


def test_refresh_chart_table_does_not_send_parameter_interval_or_plot_by(fake_client):
    fake_client.get_chart_table_rows.return_value = [
        ChartTableRow(
            id=1,
            noise_site_id=51,
            site_name="Demo Site",
            datetime="2025-01-01T00:00:00",
            conductor_and_treatment="Standard conductor (standard grease)",
            grease="standard",
            days_since_conductoring=10.0,
            leq_adj=50.0,
            tone_100hz=10.0,
            tone_200hz=5.0,
            rain1=0.0,
            rain2=0.0,
            is_wet=False,
            include=True,
        )
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table", "data")],
        inputs=[
            ("chart-init", "n_intervals", 1),
            ("chart-site-select", "value", [51]),
            ("chart-date-range", "start_date", None),
            ("chart-date-range", "end_date", None),
            ("chart-condition", "value", None),
            ("chart-conductor-treatment", "value", None),
            ("chart-grease", "value", None),
            ("chart-table-status", "children", None),
            ("chart-measurement-duration", "value", None),
            ("chart-detection-logic", "value", None),
            ("chart-table-collapse", "is_open", True),
        ],
    )

    rows = output_value(response, "chart-table", "data")
    assert len(rows) == 1
    assert rows[0]["id"] == 1

    filters = fake_client.get_chart_table_rows.call_args[0][0]
    assert filters.noise_site_id == [51]
    assert filters.condition == "all"
    assert filters.conductor_and_treatment == []
    assert filters.grease == []
    assert filters.measurement_duration == 15
    assert filters.detection_logic == "original"
    # Fields this callback's filters never set explicitly - confirm they
    # stay at ChartFilters' own defaults rather than picking up some other
    # tab's dropdown value by accident.
    assert filters.parameter == "tone_100hz"
    assert filters.interval_weeks == 2
    assert filters.plot_by == "datetime"


def test_refresh_chart_table_returns_empty_list_when_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("chart-table", "data")],
        inputs=[
            ("chart-init", "n_intervals", 1),
            ("chart-site-select", "value", None),
            ("chart-date-range", "start_date", None),
            ("chart-date-range", "end_date", None),
            ("chart-condition", "value", None),
            ("chart-conductor-treatment", "value", None),
            ("chart-grease", "value", None),
            ("chart-table-status", "children", None),
            ("chart-measurement-duration", "value", None),
            ("chart-detection-logic", "value", None),
            ("chart-table-collapse", "is_open", True),
        ],
    )

    assert output_value(response, "chart-table", "data") == []


def test_refresh_chart_table_skips_fetch_when_collapse_closed(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table", "data")],
        inputs=[
            ("chart-init", "n_intervals", 1),
            ("chart-site-select", "value", [51]),
            ("chart-date-range", "start_date", None),
            ("chart-date-range", "end_date", None),
            ("chart-condition", "value", None),
            ("chart-conductor-treatment", "value", None),
            ("chart-grease", "value", None),
            ("chart-table-status", "children", None),
            ("chart-measurement-duration", "value", None),
            ("chart-detection-logic", "value", None),
            ("chart-table-collapse", "is_open", False),
        ],
    )

    assert not fake_client.get_chart_table_rows.called
    assert response.status_code == 204


# --- save_chart_table -------------------------------------------------


def _li_texts(status_children):
    if isinstance(status_children, str):
        return [status_children]
    return [li["props"]["children"] for li in status_children["props"]["children"]]


def test_save_chart_table_no_op_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table-status", "children")],
        inputs=[("chart-table-save-button", "n_clicks", 0)],
        state=[("chart-table", "data", [])],
    )

    assert output_value(response, "chart-table-status", "children") == ""
    fake_client.update_processed_reading.assert_not_called()


def test_save_chart_table_all_rows_valid_reports_saved(fake_client):
    fake_client.update_processed_reading.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table-status", "children")],
        inputs=[("chart-table-save-button", "n_clicks", 1)],
        state=[
            (
                "chart-table",
                "data",
                [
                    {"id": 1, "is_wet": True, "include": True},
                    {"id": 2, "is_wet": False, "include": False},
                ],
            )
        ],
    )

    assert output_value(response, "chart-table-status", "children") == "Saved."
    assert fake_client.update_processed_reading.call_count == 2


def test_save_chart_table_invalid_row_is_reported_and_does_not_block_others(fake_client):
    fake_client.update_processed_reading.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table-status", "children")],
        inputs=[("chart-table-save-button", "n_clicks", 1)],
        state=[
            (
                "chart-table",
                "data",
                [
                    {"id": 1, "is_wet": "not-a-bool", "include": True},
                    {"id": 2, "is_wet": True, "include": True},
                ],
            )
        ],
    )

    status = output_value(response, "chart-table-status", "children")
    texts = _li_texts(status)
    assert len(texts) == 1
    assert "reading 1" in texts[0]

    # Row 1 failed validation before any request was made; row 2 was still
    # saved despite row 1's failure.
    assert fake_client.update_processed_reading.call_count == 1
    saved_id = fake_client.update_processed_reading.call_args[0][0]
    assert saved_id == 2


def test_save_chart_table_reports_non_200_backend_response(fake_client):
    forbidden = MagicMock(status_code=403)
    forbidden.json.return_value = {"error": "write access required"}
    fake_client.update_processed_reading.return_value = forbidden
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-table-status", "children")],
        inputs=[("chart-table-save-button", "n_clicks", 1)],
        state=[("chart-table", "data", [{"id": 5, "is_wet": True, "include": True}])],
    )

    texts = _li_texts(output_value(response, "chart-table-status", "children"))
    assert len(texts) == 1
    assert "reading 5" in texts[0]
    assert "write access required" in texts[0]


# --- export_chart_table / export_chart_plot ----------------------------


def test_export_chart_table_no_update_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-download-table", "data")],
        inputs=[("chart-export-table-button", "n_clicks", 0)],
        state=[("chart-table", "data", [{"id": 1}])],
    )

    assert response.status_code == 204


def test_export_chart_table_no_update_when_rows_empty(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-download-table", "data")],
        inputs=[("chart-export-table-button", "n_clicks", 1)],
        state=[("chart-table", "data", [])],
    )

    assert response.status_code == 204


def test_export_chart_table_builds_csv_from_current_rows(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-download-table", "data")],
        inputs=[("chart-export-table-button", "n_clicks", 1)],
        state=[("chart-table", "data", [{"id": 1, "leq_adj": 50.5}])],
    )

    payload = output_value(response, "chart-download-table", "data")
    assert payload["filename"] == "events.csv"
    assert "leq_adj" in payload["content"]
    assert "50.5" in payload["content"]


def test_export_chart_plot_no_update_for_empty_figure(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("chart-download-plot", "data")],
        inputs=[("chart-export-plot-button", "n_clicks", 1)],
        state=[("noise-chart", "figure", {"data": [], "layout": {}})],
    )

    assert response.status_code == 204


def test_export_chart_plot_builds_csv_from_plain_list_trace_data(fake_client):
    # Regression guard for the Plotly 6.x "bdata" typed-array encoding bug:
    # by the time a figure reaches this callback it must carry plain
    # Python-list x/y arrays (as chart_service._build_noise_chart guarantees
    # via .tolist()), not numpy/typed-array-shaped dicts - this locks in
    # that a well-formed figure still produces real numeric CSV rows.
    app = _build_app(fake_client)
    figure = {
        "data": [
            {
                "name": "Site 51",
                "x": ["2025-01-01T00:00:00", "2025-01-08T00:00:00"],
                "y": [48.1, 49.3],
            }
        ],
        "layout": {},
    }

    response = dispatch_callback(
        app,
        outputs=[("chart-download-plot", "data")],
        inputs=[("chart-export-plot-button", "n_clicks", 1)],
        state=[("noise-chart", "figure", figure)],
    )

    payload = output_value(response, "chart-download-plot", "data")
    assert payload["filename"] == "processed.csv"
    assert "bdata" not in payload["content"]
    assert "dtype" not in payload["content"]
    assert "Site 51" in payload["content"]
    assert "48.1" in payload["content"]
    assert "49.3" in payload["content"]
