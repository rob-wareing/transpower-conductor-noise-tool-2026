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
    # html.Div([html.P(explanation), html.Ul([html.Li(error), ...])])
    error_list = status_children["props"]["children"][1]
    return [li["props"]["children"] for li in error_list["props"]["children"]]


SAVE_OUTPUTS = [
    ("outages-status", "children"),
    ("outages-table", "data"),
    ("outages-table", "columns"),
    ("outages-loaded-ids", "data"),
]
COLUMNS = [{"name": "Notes", "id": "notes"}]


def _save(app, rows, loaded_ids, n_clicks=1, columns=COLUMNS):
    return dispatch_callback(
        app,
        outputs=SAVE_OUTPUTS,
        inputs=[("outages-save-button", "n_clicks", n_clicks)],
        state=[
            ("outages-table", "data", rows),
            ("outages-loaded-ids", "data", loaded_ids),
            ("outages-table", "columns", columns),
        ],
    )


def _new_row(**overrides):
    fields = {
        "noise_site_id": 51,
        "outage_type": "line",
        "start_datetime": "2025-02-01T00:00:00",
        "end_datetime": "2025-02-01T02:00:00",
        "notes": "brand new",
    }
    fields.update(overrides)
    return fields


def _failed_response(status_code, error):
    response = MagicMock(status_code=status_code)
    response.json.return_value = {"error": error}
    return response


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


def test_refresh_outages_table_returns_pass_through_rows_and_loaded_ids(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1), _outage(id=7)]
    app = _build_app(fake_client)

    response = dispatch_callback(
        app,
        outputs=[("outages-table", "data"), ("outages-loaded-ids", "data")],
        inputs=[("outages-init", "n_intervals", 1)],
    )

    rows = output_value(response, "outages-table", "data")
    assert [row["id"] for row in rows] == [1, 7]
    assert rows[0]["noise_site_id"] == 51
    assert output_value(response, "outages-loaded-ids", "data") == [1, 7]


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


# --- save_outages ----------------------------------------------------------


def test_save_outages_no_op_when_not_clicked(fake_client):
    app = _build_app(fake_client)

    response = _save(app, [], [], n_clicks=0)

    assert output_value(response, "outages-status", "children") == ""
    fake_client.get_outages.assert_not_called()


def test_save_outages_deletes_only_rows_removed_since_load(fake_client):
    # Loaded with 1 and 2; the user removed 1. Row 3 was added by someone
    # else after this table loaded - it must NOT be deleted.
    fake_client.get_outages.return_value = [_outage(id=2), _outage(id=3)]
    fake_client.delete_outage.return_value = MagicMock(status_code=200)
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    _save(app, [_outage(id=2).model_dump(mode="json")], loaded_ids=[1, 2])

    fake_client.delete_outage.assert_called_once()
    assert fake_client.delete_outage.call_args[0][0] == 1


def test_save_outages_delete_of_already_deleted_row_is_not_an_error(fake_client):
    fake_client.get_outages.return_value = []
    fake_client.delete_outage.return_value = _failed_response(404, "outage not found")
    app = _build_app(fake_client)

    response = _save(app, [], loaded_ids=[1])

    assert output_value(response, "outages-status", "children") == "Saved."


def test_save_outages_failed_delete_is_reported_and_row_highlighted(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1)]
    fake_client.delete_outage.return_value = _failed_response(500, "boom")
    app = _build_app(fake_client)

    response = _save(app, [], loaded_ids=[1])

    texts = _li_texts(output_value(response, "outages-status", "children"))
    assert len(texts) == 1
    assert "delete outage 1" in texts[0]
    assert "boom" in texts[0]
    rows = output_value(response, "outages-table", "data")
    assert rows[0]["id"] == 1
    assert rows[0]["save_error"] == "delete failed: boom"


def test_save_outages_row_with_id_goes_through_update(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1)]
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    _save(app, [_outage(id=1, notes="updated").model_dump(mode="json")], loaded_ids=[1])

    fake_client.update_outage.assert_called_once()
    assert fake_client.update_outage.call_args[0][0] == 1
    fake_client.create_outage.assert_not_called()


def test_save_outages_blank_new_row_is_silently_skipped(fake_client):
    fake_client.get_outages.return_value = []
    app = _build_app(fake_client)

    blank_row = {field: "" for field in outages_callbacks.EDITABLE_FIELDS}
    response = _save(app, [blank_row], loaded_ids=[])

    assert output_value(response, "outages-status", "children") == "Saved."
    assert output_value(response, "outages-table", "data") == []
    fake_client.create_outage.assert_not_called()


def test_save_outages_new_row_validation_failure_is_kept_in_table(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1)]
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    app = _build_app(fake_client)

    invalid_row = _new_row(end_datetime="2025-02-01T00:00:00")  # not after start
    response = _save(app, [_outage(id=1).model_dump(mode="json"), invalid_row], loaded_ids=[1])

    texts = _li_texts(output_value(response, "outages-status", "children"))
    assert len(texts) == 1
    assert "new outage" in texts[0]
    fake_client.create_outage.assert_not_called()

    rows = output_value(response, "outages-table", "data")
    assert [row.get("id") for row in rows] == [1, None]
    assert "save_error" not in rows[0]
    assert rows[1]["notes"] == "brand new"
    assert "end_datetime must be after start_datetime" in rows[1]["save_error"]
    columns = output_value(response, "outages-table", "columns")
    assert columns[-1]["id"] == "save_error"


def test_save_outages_new_row_rejected_by_backend_is_kept_with_reason(fake_client):
    fake_client.get_outages.return_value = []
    fake_client.create_outage.return_value = _failed_response(
        400, "unknown outage_type 'line' or site"
    )
    app = _build_app(fake_client)

    response = _save(app, [_new_row(noise_site_id=260)], loaded_ids=[])

    rows = output_value(response, "outages-table", "data")
    assert rows[0]["noise_site_id"] == 260
    assert rows[0]["save_error"] == "unknown outage_type 'line' or site"


def test_save_outages_backend_validation_error_list_reports_first_message(fake_client):
    fake_client.get_outages.return_value = []
    fake_client.create_outage.return_value = _failed_response(
        400, [{"type": "datetime_parsing", "msg": "Input should be a valid datetime"}]
    )
    app = _build_app(fake_client)

    response = _save(app, [_new_row()], loaded_ids=[])

    rows = output_value(response, "outages-table", "data")
    assert rows[0]["save_error"] == "Input should be a valid datetime"


def test_save_outages_non_json_server_error_is_reported_not_raised(fake_client):
    fake_client.get_outages.return_value = []
    html_error = MagicMock(status_code=500)
    html_error.json.side_effect = ValueError("not JSON")
    fake_client.create_outage.return_value = html_error
    app = _build_app(fake_client)

    response = _save(app, [_new_row()], loaded_ids=[])

    texts = _li_texts(output_value(response, "outages-status", "children"))
    assert texts == ["new outage: server error (HTTP 500)"]
    assert output_value(response, "outages-table", "data")[0]["notes"] == "brand new"


def test_save_outages_failed_update_keeps_users_values_not_server_values(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1, notes="server copy")]
    fake_client.update_outage.return_value = _failed_response(400, "unknown outage_type")
    app = _build_app(fake_client)

    edited = _outage(id=1, notes="my edit").model_dump(mode="json")
    response = _save(app, [edited], loaded_ids=[1])

    rows = output_value(response, "outages-table", "data")
    assert len(rows) == 1
    assert rows[0]["notes"] == "my edit"
    assert rows[0]["save_error"] == "unknown outage_type"


def test_save_outages_failed_update_of_row_deleted_elsewhere_is_still_shown(fake_client):
    fake_client.get_outages.return_value = []
    fake_client.update_outage.return_value = _failed_response(404, "outage not found")
    app = _build_app(fake_client)

    edited = _outage(id=1, notes="my edit").model_dump(mode="json")
    response = _save(app, [edited], loaded_ids=[1])

    rows = output_value(response, "outages-table", "data")
    assert rows[0]["notes"] == "my edit"
    assert rows[0]["save_error"] == "outage not found"


def test_save_outages_success_clears_previous_errors_and_error_column(fake_client):
    fake_client.get_outages.return_value = [_outage(id=1), _outage(id=2, notes="brand new")]
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    fake_client.create_outage.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    retried = {**_new_row(), "save_error": "unknown outage_type 'line' or site"}
    columns = COLUMNS + [outages_callbacks.SAVE_ERROR_COLUMN]
    response = _save(
        app, [_outage(id=1).model_dump(mode="json"), retried], loaded_ids=[1], columns=columns
    )

    assert output_value(response, "outages-status", "children") == "Saved."
    rows = output_value(response, "outages-table", "data")
    assert all("save_error" not in row for row in rows)
    assert output_value(response, "outages-table", "columns") == COLUMNS
    assert output_value(response, "outages-loaded-ids", "data") == [1, 2]
    # save_error is display-only - never sent to the backend.
    sent = fake_client.create_outage.call_args[0][0]
    assert "save_error" not in sent.model_dump()


def test_save_outages_mixed_batch_deletes_updates_creates_and_skips_blank(fake_client):
    fake_client.get_outages.return_value = [_outage(id=2, notes="fresh"), _outage(id=3)]
    fake_client.delete_outage.return_value = MagicMock(status_code=200)
    fake_client.update_outage.return_value = MagicMock(status_code=200)
    fake_client.create_outage.return_value = MagicMock(status_code=201)
    app = _build_app(fake_client)

    rows = [
        # id=1 removed by the user -> should be deleted.
        _outage(id=2, notes="fresh").model_dump(mode="json"),  # update
        _new_row(),  # create
        {field: "" for field in outages_callbacks.EDITABLE_FIELDS},  # blank - skipped
    ]

    response = _save(app, rows, loaded_ids=[1, 2])

    assert output_value(response, "outages-status", "children") == "Saved."
    assert fake_client.delete_outage.call_args[0][0] == 1
    assert fake_client.update_outage.call_args[0][0] == 2
    fake_client.create_outage.assert_called_once()
    assert [row["id"] for row in output_value(response, "outages-table", "data")] == [2, 3]


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
