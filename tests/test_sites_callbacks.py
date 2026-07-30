from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import sites as sites_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import sites as sites_layout
from transpower_conductor_noise_tool_2026.shared.contracts import SiteDetail

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = sites_layout.content(write_access=True)
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.sites.BackendClient",
            return_value=fake_client,
        ):
            sites_callbacks.register_callbacks(app, backend_url)
    else:
        sites_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


def _li_texts(status_children):
    if isinstance(status_children, str):
        return [status_children]
    return [li["props"]["children"] for li in status_children["props"]["children"]]


def _row(**overrides):
    fields = {
        "noise_site_id": 51,
        "site_code": "DS",
        "plot_color": "#aabbcc",
        "height_adj_db": 1.5,
        "data_folder": None,
        "report_folder": None,
        "latitude": None,
        "longitude": None,
    }
    fields.update(overrides)
    return fields


# --- refresh_sites_table ---------------------------------------------


def test_refresh_sites_table_returns_site_details(fake_client):
    fake_client.get_site_details.return_value = [
        SiteDetail(
            noise_site_id=51,
            site_name="Demo Site",
            site_code="DS",
            latitude=-41.0,
            longitude=174.9,
        ),
    ]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-table", "data")],
        inputs=[("sites-init", "n_intervals", 1), ("sites-status", "children", None)],
    )

    rows = output_value(response, "sites-table", "data")
    assert len(rows) == 1
    assert rows[0]["noise_site_id"] == 51
    assert rows[0]["latitude"] == -41.0


def test_refresh_sites_table_empty_when_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("sites-table", "data")],
        inputs=[("sites-init", "n_intervals", 1), ("sites-status", "children", None)],
    )

    assert output_value(response, "sites-table", "data") == []


# --- save_sites ---------------------------------------------------------


def test_save_sites_no_op_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-status", "children")],
        inputs=[("sites-save-button", "n_clicks", 0)],
        state=[("sites-table", "data", [])],
    )

    assert output_value(response, "sites-status", "children") == ""
    fake_client.update_site.assert_not_called()


def test_save_sites_all_rows_valid_reports_saved(fake_client):
    fake_client.update_site.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-status", "children")],
        inputs=[("sites-save-button", "n_clicks", 1)],
        state=[("sites-table", "data", [_row()])],
    )

    assert output_value(response, "sites-status", "children") == "Saved."
    fake_client.update_site.assert_called_once()
    assert fake_client.update_site.call_args[0][0] == 51


def test_save_sites_reports_non_200_backend_response(fake_client):
    forbidden = MagicMock(status_code=403)
    forbidden.json.return_value = {"error": "write access required"}
    fake_client.update_site.return_value = forbidden
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-status", "children")],
        inputs=[("sites-save-button", "n_clicks", 1)],
        state=[("sites-table", "data", [_row()])],
    )

    texts = _li_texts(output_value(response, "sites-status", "children"))
    assert len(texts) == 1
    assert "site 51" in texts[0]
    assert "write access required" in texts[0]


def test_save_sites_invalid_row_is_reported_and_does_not_block_others(fake_client):
    # Regression test: save_sites used to build SiteUpdate(**fields) without
    # catching ValidationError, unlike every other write-tab callback - an
    # out-of-range latitude would crash the callback (HTTP 500) instead of
    # being reported as a friendly per-row error like this.
    fake_client.update_site.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-status", "children")],
        inputs=[("sites-save-button", "n_clicks", 1)],
        state=[
            (
                "sites-table",
                "data",
                [
                    _row(noise_site_id=51, latitude=999),
                    _row(noise_site_id=52),
                ],
            )
        ],
    )

    assert response.status_code == 200
    texts = _li_texts(output_value(response, "sites-status", "children"))
    assert len(texts) == 1
    assert "site 51" in texts[0]

    assert fake_client.update_site.call_count == 1
    assert fake_client.update_site.call_args[0][0] == 52


# --- export_sites ---------------------------------------------------------


def test_export_sites_no_update_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-download", "data")],
        inputs=[("sites-export-button", "n_clicks", 0)],
        state=[("sites-table", "data", [_row()])],
    )

    assert response.status_code == 204


def test_export_sites_no_update_when_rows_empty(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-download", "data")],
        inputs=[("sites-export-button", "n_clicks", 1)],
        state=[("sites-table", "data", [])],
    )

    assert response.status_code == 204


def test_export_sites_builds_csv_from_current_rows(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("sites-download", "data")],
        inputs=[("sites-export-button", "n_clicks", 1)],
        state=[("sites-table", "data", [_row()])],
    )

    payload = output_value(response, "sites-download", "data")
    assert payload["filename"] == "sites.csv"
    assert "site_code" in payload["content"]
    assert "DS" in payload["content"]
