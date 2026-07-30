from unittest.mock import MagicMock, patch

import dash
import pytest

from transpower_conductor_noise_tool_2026.frontend.callbacks import (
    reconductoring as reconductoring_callbacks,
)
from transpower_conductor_noise_tool_2026.frontend.client import BackendClient
from transpower_conductor_noise_tool_2026.frontend.layout import reconductoring as reconductoring_layout
from transpower_conductor_noise_tool_2026.shared.contracts import ReconductoringDetail

from .dash_callback_utils import dispatch_callback, output_value


def _build_app(fake_client=None, backend_url="http://fake-backend"):
    app = dash.Dash(__name__)
    app.config.suppress_callback_exceptions = True
    app.layout = reconductoring_layout.content(write_access=True)
    if backend_url:
        with patch(
            "transpower_conductor_noise_tool_2026.frontend.callbacks.reconductoring.BackendClient",
            return_value=fake_client,
        ):
            reconductoring_callbacks.register_callbacks(app, backend_url)
    else:
        reconductoring_callbacks.register_callbacks(app, backend_url)
    return app


@pytest.fixture
def fake_client():
    return MagicMock(spec=BackendClient)


def _li_texts(status_children):
    if isinstance(status_children, str):
        return [status_children]
    return [li["props"]["children"] for li in status_children["props"]["children"]]


def _event(**overrides):
    fields = {
        "id": 1,
        "noise_site_id": 51,
        "conductor_and_treatment": "Standard conductor (standard grease)",
        "grease": "standard",
        "reconductoring_date": "2024-11-15",
        "notes": None,
    }
    fields.update(overrides)
    return ReconductoringDetail(**fields)


# --- EDITABLE_FIELDS never exposes conductor/plot_linestyle ---------------


def test_editable_fields_never_expose_hidden_model_only_columns():
    # `conductor` and `plot_linestyle` exist on the Reconductoring model for
    # schema fidelity with the old app, but neither the old UI nor this one
    # ever showed/edited them - guard against either leaking into the
    # editable table (and from there, into a create/update payload).
    assert "conductor" not in reconductoring_callbacks.EDITABLE_FIELDS
    assert "plot_linestyle" not in reconductoring_callbacks.EDITABLE_FIELDS


# --- refresh_reconductoring_table -----------------------------------------


def test_refresh_reconductoring_table_returns_pass_through_rows(fake_client):
    fake_client.get_reconductoring_events.return_value = [_event()]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("reconductoring-table", "data")],
        inputs=[
            ("reconductoring-init", "n_intervals", 1),
            ("reconductoring-status", "children", None),
        ],
    )

    rows = output_value(response, "reconductoring-table", "data")
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["conductor_and_treatment"] == "Standard conductor (standard grease)"


# --- add_row ---------------------------------------------------------------


def test_add_row_appends_blank_row_keyed_by_editable_fields(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("reconductoring-table", "data")],
        inputs=[("reconductoring-add-row-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [])],
    )

    rows = output_value(response, "reconductoring-table", "data")
    assert rows == [{field: "" for field in reconductoring_callbacks.EDITABLE_FIELDS}]


# --- save_reconductoring (diff-against-server-truth) -----------------


def test_save_reconductoring_no_op_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 0)],
        state=[("reconductoring-table", "data", [])],
    )

    assert output_value(response, "reconductoring-status", "children") == ""
    fake_client.get_reconductoring_events.assert_not_called()


def test_save_reconductoring_deletes_rows_missing_from_submitted_table(fake_client):
    fake_client.get_reconductoring_events.return_value = [_event(id=1), _event(id=2)]
    fake_client.delete_reconductoring_event.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [_event(id=2).model_dump(mode="json")])],
    )

    fake_client.delete_reconductoring_event.assert_called_once()
    assert fake_client.delete_reconductoring_event.call_args[0][0] == 1


def test_save_reconductoring_row_with_id_goes_through_update(fake_client):
    fake_client.get_reconductoring_events.return_value = [_event(id=1)]
    fake_client.update_reconductoring_event.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    row = _event(id=1, notes="updated").model_dump(mode="json")
    dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [row])],
    )

    fake_client.update_reconductoring_event.assert_called_once()
    assert fake_client.update_reconductoring_event.call_args[0][0] == 1
    fake_client.create_reconductoring_event.assert_not_called()


def test_save_reconductoring_blank_new_row_is_silently_skipped(fake_client):
    fake_client.get_reconductoring_events.return_value = []
    app = _build_app(fake_client)

    blank_row = {field: "" for field in reconductoring_callbacks.EDITABLE_FIELDS}
    response = dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [blank_row])],
    )

    assert output_value(response, "reconductoring-status", "children") == "Saved."
    fake_client.create_reconductoring_event.assert_not_called()


def test_save_reconductoring_new_row_is_created(fake_client):
    fake_client.get_reconductoring_events.return_value = []
    fake_client.create_reconductoring_event.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    new_row = {
        "noise_site_id": 51,
        "conductor_and_treatment": "New conductor",
        "grease": "synthetic",
        "reconductoring_date": "2025-01-01",
        "notes": None,
    }
    response = dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [new_row])],
    )

    assert output_value(response, "reconductoring-status", "children") == "Saved."
    fake_client.create_reconductoring_event.assert_called_once()


def test_save_reconductoring_new_row_validation_failure_is_reported(fake_client):
    fake_client.get_reconductoring_events.return_value = []
    app = _build_app(fake_client)

    # reconductoring_date is required and not parseable as a date.
    invalid_row = {
        "noise_site_id": 51,
        "conductor_and_treatment": "New conductor",
        "grease": "synthetic",
        "reconductoring_date": "not-a-date",
        "notes": None,
    }
    response = dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [invalid_row])],
    )

    texts = _li_texts(output_value(response, "reconductoring-status", "children"))
    assert len(texts) == 1
    assert "new event" in texts[0]
    fake_client.create_reconductoring_event.assert_not_called()


def test_save_reconductoring_mixed_batch_deletes_updates_creates_and_skips_blank(fake_client):
    fake_client.get_reconductoring_events.return_value = [_event(id=1), _event(id=2, notes="stale")]
    fake_client.delete_reconductoring_event.return_value = MagicMock(status_code=200)
    fake_client.update_reconductoring_event.return_value = MagicMock(status_code=200)
    fake_client.create_reconductoring_event.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    rows = [
        # id=1 omitted entirely -> should be deleted.
        _event(id=2, notes="fresh").model_dump(mode="json"),  # update
        {
            "noise_site_id": 52,
            "conductor_and_treatment": "New conductor",
            "grease": "synthetic",
            "reconductoring_date": "2025-01-01",
            "notes": "brand new",
        },  # create
        {field: "" for field in reconductoring_callbacks.EDITABLE_FIELDS},  # blank - skipped
    ]

    response = dispatch_callback(
        app,
        outputs=[("reconductoring-status", "children")],
        inputs=[("reconductoring-save-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", rows)],
    )

    assert output_value(response, "reconductoring-status", "children") == "Saved."
    assert fake_client.delete_reconductoring_event.call_args[0][0] == 1
    assert fake_client.update_reconductoring_event.call_args[0][0] == 2
    fake_client.create_reconductoring_event.assert_called_once()


# --- export_reconductoring -------------------------------------------------


def test_export_reconductoring_no_update_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("reconductoring-download", "data")],
        inputs=[("reconductoring-export-button", "n_clicks", 0)],
        state=[("reconductoring-table", "data", [{"id": 1}])],
    )

    assert response.status_code == 204


def test_export_reconductoring_builds_csv_from_current_rows(fake_client):
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("reconductoring-download", "data")],
        inputs=[("reconductoring-export-button", "n_clicks", 1)],
        state=[("reconductoring-table", "data", [_event().model_dump(mode="json")])],
    )

    payload = output_value(response, "reconductoring-download", "data")
    assert payload["filename"] == "reconductoring.csv"
    assert "Standard conductor (standard grease)" in payload["content"]
