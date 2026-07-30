from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import outages as outages_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import outages as outages_layout
from transpower_conductor_noise_tool_2026.shared.contracts import OutageDetail

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = outages_layout.content(write_access=True)
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.outages.BackendClient",
            return_value=fake_client,
        ):
            outages_callbacks.register_callbacks(app, backend_url)
    else:
        outages_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


def _li_texts(status_children):
    if isinstance(status_children, str):
        return [status_children]
    return [li["props"]["children"] for li in status_children["props"]["children"]]


def _outage(**overrides):
    fields = {
        "id": 1,
        "noise_site_id": 51,
        "outage_type": "monitoring",
        "start_datetime": "2025-01-01T00:00:00",
        "end_datetime": "2025-01-01T01:00:00",
        "notes": None,
    }
    fields.update(overrides)
    return OutageDetail(**fields)


# --- populate_outage_type_options ---------------------------------------


def test_populate_outage_type_options_returns_dropdown_column_shape(fake_client):
    fake_client.get_outage_types.return_value = ["monitoring", "line"]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-table", "dropdown")],
        inputs=[("outages-init", "n_intervals", 1)],
    )

    assert output_value(response, "outages-table", "dropdown") == {
        "outage_type": {
            "options": [
                {"label": "monitoring", "value": "monitoring"},
                {"label": "line", "value": "line"},
            ]
        }
    }


def test_populate_outage_type_options_empty_when_no_backend():
    app = _build_app(fake_client=None, backend_url=None)

    response = dispatch_callback(
        app,
        outputs=[("outages-table", "dropdown")],
        inputs=[("outages-init", "n_intervals", 1)],
    )

    assert output_value(response, "outages-table", "dropdown") == {}


# --- refresh_outages_table ------------------------------------------------


def test_refresh_outages_table_returns_pass_through_rows(fake_client):
    fake_client.get_outages.return_value = [_outage()]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-table", "data")],
        inputs=[("outages-init", "n_intervals", 1), ("outages-status", "children", None)],
    )

    rows = output_value(response, "outages-table", "data")
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["noise_site_id"] == 51


# --- add_row ---------------------------------------------------------------


def test_add_row_ignores_falsy_n_clicks(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-table", "data")],
        inputs=[("outages-add-row-button", "n_clicks", 0)],
        state=[("outages-table", "data", [{"id": 1}])],
    )

    assert output_value(response, "outages-table", "data") == [{"id": 1}]


def test_add_row_appends_blank_row_keyed_by_editable_fields(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-table", "data")],
        inputs=[("outages-add-row-button", "n_clicks", 1)],
        state=[("outages-table", "data", [{"id": 1}])],
    )

    rows = output_value(response, "outages-table", "data")
    assert rows[0] == {"id": 1}
    assert rows[1] == {field: "" for field in outages_callbacks.EDITABLE_FIELDS}


# --- save_outages (diff-against-server-truth) -------------------------


def test_save_outages_no_op_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 0)],
        state=[("outages-table", "data", [])],
    )

    assert output_value(response, "outages-status", "children") == ""
    fake_client.get_outages.assert_not_called()


def test_save_outages_deletes_rows_missing_from_submitted_table(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1), _outage(id=2)]
    fake_client.delete_outage.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 1)],
        state=[("outages-table", "data", [_outage(id=2).model_dump(mode="json")])],
    )

    fake_client.delete_outage.assert_called_once()
    assert fake_client.delete_outage.call_args[0][0] == 1


def test_save_outages_failed_delete_is_reported_but_does_not_abort(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1)]
    failed = MagicMock(status_code=500)
    failed.json.return_value = {"error": "boom"}
    fake_client.delete_outage.return_value = failed
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 1)],
        state=[("outages-table", "data", [])],
    )

    texts = _li_texts(output_value(response, "outages-status", "children"))
    assert len(texts) == 1
    assert "delete outage 1" in texts[0]
    assert "boom" in texts[0]


def test_save_outages_row_with_id_goes_through_update(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1)]
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    row = _outage(id=1, notes="updated").model_dump(mode="json")
    dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 1)],
        state=[("outages-table", "data", [row])],
    )

    fake_client.update_outage.assert_called_once()
    assert fake_client.update_outage.call_args[0][0] == 1
    fake_client.create_outage.assert_not_called()


def test_save_outages_blank_new_row_is_silently_skipped(fake_client):
    fake_client.get_outages.return_value = []
    app = _build_app(fake_client)

    blank_row = {field: "" for field in outages_callbacks.EDITABLE_FIELDS}
    response = dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 1)],
        state=[("outages-table", "data", [blank_row])],
    )

    assert output_value(response, "outages-status", "children") == "Saved."
    fake_client.create_outage.assert_not_called()


def test_save_outages_new_row_validation_failure_is_reported(fake_client):
    fake_client.get_outages.return_value = []
    app = _build_app(fake_client)

    invalid_row = {
        "noise_site_id": 51,
        "outage_type": "monitoring",
        "start_datetime": "2025-01-01T00:00:00",
        "end_datetime": "2025-01-01T00:00:00",  # not after start - invalid
        "notes": None,
    }
    response = dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 1)],
        state=[("outages-table", "data", [invalid_row])],
    )

    texts = _li_texts(output_value(response, "outages-status", "children"))
    assert len(texts) == 1
    assert "new outage" in texts[0]
    fake_client.create_outage.assert_not_called()


def test_save_outages_mixed_batch_deletes_updates_creates_and_skips_blank(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1), _outage(id=2, notes="stale")]
    fake_client.delete_outage.return_value = MagicMock(status_code=200)
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    fake_client.create_outage.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    rows = [
        # id=1 omitted entirely -> should be deleted.
        _outage(id=2, notes="fresh").model_dump(mode="json"),  # update
        {
            "noise_site_id": 51,
            "outage_type": "line",
            "start_datetime": "2025-02-01T00:00:00",
            "end_datetime": "2025-02-01T02:00:00",
            "notes": "brand new",
        },  # create
        {field: "" for field in outages_callbacks.EDITABLE_FIELDS},  # blank - skipped
    ]

    response = dispatch_callback(
        app,
        outputs=[("outages-status", "children")],
        inputs=[("outages-save-button", "n_clicks", 1)],
        state=[("outages-table", "data", rows)],
    )

    assert output_value(response, "outages-status", "children") == "Saved."
    assert fake_client.delete_outage.call_args[0][0] == 1
    assert fake_client.update_outage.call_args[0][0] == 2
    fake_client.create_outage.assert_called_once()


# --- export_outages ------------------------------------------------------


def test_export_outages_no_update_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-download", "data")],
        inputs=[("outages-export-button", "n_clicks", 0)],
        state=[("outages-table", "data", [{"id": 1}])],
    )

    assert response.status_code == 204


def test_export_outages_builds_csv_from_current_rows(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-download", "data")],
        inputs=[("outages-export-button", "n_clicks", 1)],
        state=[("outages-table", "data", [_outage().model_dump(mode="json")])],
    )

    payload = output_value(response, "outages-download", "data")
    assert payload["filename"] == "outages.csv"
    assert "monitoring" in payload["content"]
