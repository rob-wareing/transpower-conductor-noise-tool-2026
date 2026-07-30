from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import historical as historical_callbacks
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import historical as historical_layout
from transpower_conductor_noise_tool_2026.shared.contracts import HistoricalResultDetail

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = historical_layout.content(write_access=True)
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.historical.BackendClient",
            return_value=fake_client,
        ):
            historical_callbacks.register_callbacks(app, backend_url)
    else:
        historical_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


def _li_texts(status_children):
    if isinstance(status_children, str):
        return [status_children]
    return [li["props"]["children"] for li in status_children["props"]["children"]]


def _result(**overrides):
    fields = {
        "id": 1,
        "noise_site_id": 51,
        "period_length": 2,
        "period_end_date": "2019-06-01",
        "leq_adj": 48.5,
        "tone_100hz": 10.4,
    }
    fields.update(overrides)
    return HistoricalResultDetail(**fields)


# --- EDITABLE_FIELDS never exposes the hidden period_length column --------


def test_editable_fields_never_expose_period_length():
    # The old app's UI hides period_length entirely (it's 2 for every real
    # row); HistoricalResultCreate defaults it server-side, so this callback
    # must never try to submit it as a user-edited field.
    assert "period_length" not in historical_callbacks.EDITABLE_FIELDS


# --- refresh_historical_table ---------------------------------------------


def test_refresh_historical_table_returns_pass_through_rows(fake_client):
    fake_client.get_historical_results.return_value = [_result()]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("historical-table", "data")],
        inputs=[("historical-init", "n_intervals", 1), ("historical-status", "children", None)],
    )

    rows = output_value(response, "historical-table", "data")
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["leq_adj"] == 48.5


# --- add_row ---------------------------------------------------------------


def test_add_row_appends_blank_row_keyed_by_editable_fields(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("historical-table", "data")],
        inputs=[("historical-add-row-button", "n_clicks", 1)],
        state=[("historical-table", "data", [])],
    )

    rows = output_value(response, "historical-table", "data")
    assert rows == [{field: "" for field in historical_callbacks.EDITABLE_FIELDS}]


# --- save_historical (diff-against-server-truth) -----------------------


def test_save_historical_no_op_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 0)],
        state=[("historical-table", "data", [])],
    )

    assert output_value(response, "historical-status", "children") == ""
    fake_client.get_historical_results.assert_not_called()


def test_save_historical_deletes_rows_missing_from_submitted_table(fake_client):
    fake_client.get_historical_results.return_value = [_result(id=1), _result(id=2)]
    fake_client.delete_historical_result.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 1)],
        state=[("historical-table", "data", [_result(id=2).model_dump(mode="json")])],
    )

    fake_client.delete_historical_result.assert_called_once()
    assert fake_client.delete_historical_result.call_args[0][0] == 1


def test_save_historical_row_with_id_goes_through_update(fake_client):
    fake_client.get_historical_results.return_value = [_result(id=1)]
    fake_client.update_historical_result.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    row = _result(id=1, leq_adj=51.0).model_dump(mode="json")
    dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 1)],
        state=[("historical-table", "data", [row])],
    )

    fake_client.update_historical_result.assert_called_once()
    assert fake_client.update_historical_result.call_args[0][0] == 1
    fake_client.create_historical_result.assert_not_called()


def test_save_historical_blank_new_row_is_silently_skipped(fake_client):
    fake_client.get_historical_results.return_value = []
    app = _build_app(fake_client)

    blank_row = {field: "" for field in historical_callbacks.EDITABLE_FIELDS}
    response = dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 1)],
        state=[("historical-table", "data", [blank_row])],
    )

    assert output_value(response, "historical-status", "children") == "Saved."
    fake_client.create_historical_result.assert_not_called()


def test_save_historical_new_row_is_created(fake_client):
    fake_client.get_historical_results.return_value = []
    fake_client.create_historical_result.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    new_row = {
        "noise_site_id": 51,
        "period_end_date": "2025-01-01",
        "leq_adj": 48.5,
        "tone_100hz": 10.4,
    }
    response = dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 1)],
        state=[("historical-table", "data", [new_row])],
    )

    assert output_value(response, "historical-status", "children") == "Saved."
    fake_client.create_historical_result.assert_called_once()


def test_save_historical_new_row_validation_failure_is_reported(fake_client):
    fake_client.get_historical_results.return_value = []
    app = _build_app(fake_client)

    # period_end_date is required and not parseable as a date.
    invalid_row = {
        "noise_site_id": 51,
        "period_end_date": "not-a-date",
        "leq_adj": 48.5,
        "tone_100hz": 10.4,
    }
    response = dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 1)],
        state=[("historical-table", "data", [invalid_row])],
    )

    texts = _li_texts(output_value(response, "historical-status", "children"))
    assert len(texts) == 1
    assert "new result" in texts[0]
    fake_client.create_historical_result.assert_not_called()


def test_save_historical_mixed_batch_deletes_updates_creates_and_skips_blank(fake_client):
    fake_client.get_historical_results.return_value = [_result(id=1), _result(id=2)]
    fake_client.delete_historical_result.return_value = MagicMock(status_code=200)
    fake_client.update_historical_result.return_value = MagicMock(status_code=200)
    fake_client.create_historical_result.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    rows = [
        # id=1 omitted entirely -> should be deleted.
        _result(id=2, leq_adj=52.0).model_dump(mode="json"),  # update
        {
            "noise_site_id": 52,
            "period_end_date": "2025-01-01",
            "leq_adj": 47.0,
            "tone_100hz": 9.0,
        },  # create
        {field: "" for field in historical_callbacks.EDITABLE_FIELDS},  # blank - skipped
    ]

    response = dispatch_callback(
        app,
        outputs=[("historical-status", "children")],
        inputs=[("historical-save-button", "n_clicks", 1)],
        state=[("historical-table", "data", rows)],
    )

    assert output_value(response, "historical-status", "children") == "Saved."
    assert fake_client.delete_historical_result.call_args[0][0] == 1
    assert fake_client.update_historical_result.call_args[0][0] == 2
    fake_client.create_historical_result.assert_called_once()


# --- export_historical -------------------------------------------------


def test_export_historical_no_update_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("historical-download", "data")],
        inputs=[("historical-export-button", "n_clicks", 0)],
        state=[("historical-table", "data", [{"id": 1}])],
    )

    assert response.status_code == 204


def test_export_historical_builds_csv_from_current_rows(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("historical-download", "data")],
        inputs=[("historical-export-button", "n_clicks", 1)],
        state=[("historical-table", "data", [_result().model_dump(mode="json")])],
    )

    payload = output_value(response, "historical-download", "data")
    assert payload["filename"] == "historical.csv"
    assert "48.5" in payload["content"]
