from transpower_conductor_noise_tool_2026.backend.app import create_app


def _make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app, app.test_client()


def _login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@transpower.example", "password": "demo-password"},
    )
    assert response.status_code == 200


def test_outages_endpoint_returns_seeded_rows(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/outages")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] > 0
    assert {"noise_site_id", "outage_type", "start_datetime", "end_datetime"} <= set(
        payload["items"][0].keys()
    )


def test_outage_types_endpoint_returns_seeded_types(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/outages/types")

    assert response.status_code == 200
    assert set(response.get_json()["items"]) == {"monitoring", "line"}


def test_create_outage_requires_authentication(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/outages",
        json={
            "noise_site_id": 51,
            "outage_type": "monitoring",
            "start_datetime": "2025-01-01T00:00:00",
            "end_datetime": "2025-01-01T01:00:00",
        },
    )

    assert response.status_code == 401


def test_create_outage_with_write_access_persists(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/api/outages",
        json={
            "noise_site_id": 51,
            "outage_type": "monitoring",
            "start_datetime": "2025-06-01T00:00:00",
            "end_datetime": "2025-06-01T02:00:00",
            "notes": "Test outage",
        },
    )

    assert response.status_code == 201
    outage = response.get_json()["outage"]
    assert outage["notes"] == "Test outage"

    list_response = client.get("/api/outages")
    assert any(item["id"] == outage["id"] for item in list_response.get_json()["items"])


def test_create_outage_rejects_end_before_start(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/api/outages",
        json={
            "noise_site_id": 51,
            "outage_type": "monitoring",
            "start_datetime": "2025-06-01T02:00:00",
            "end_datetime": "2025-06-01T00:00:00",
        },
    )

    assert response.status_code == 400


def test_create_outage_rejects_unknown_outage_type(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/api/outages",
        json={
            "noise_site_id": 51,
            "outage_type": "not-a-real-type",
            "start_datetime": "2025-06-01T00:00:00",
            "end_datetime": "2025-06-01T02:00:00",
        },
    )

    assert response.status_code == 400


def test_update_outage_requires_write_access(tmp_path, monkeypatch):
    from transpower_conductor_noise_tool_2026.backend.domain.auth_service import create_user

    app, client = _make_client(tmp_path, monkeypatch)
    with app.app_context():
        create_user("Read Only", "readonly@transpower.example", "password", write_access=False)
    client.post(
        "/api/auth/login", json={"email": "readonly@transpower.example", "password": "password"}
    )

    response = client.patch("/api/outages/1", json={"notes": "hacked"})

    assert response.status_code == 403


def test_update_outage_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/outages/999999", json={"notes": "x"})

    assert response.status_code == 404


def test_delete_outage_removes_it(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    create_response = client.post(
        "/api/outages",
        json={
            "noise_site_id": 51,
            "outage_type": "line",
            "start_datetime": "2025-07-01T00:00:00",
            "end_datetime": "2025-07-01T01:00:00",
        },
    )
    outage_id = create_response.get_json()["outage"]["id"]

    delete_response = client.delete(f"/api/outages/{outage_id}")
    assert delete_response.status_code == 200

    list_response = client.get("/api/outages")
    assert all(item["id"] != outage_id for item in list_response.get_json()["items"])


def test_delete_outage_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.delete("/api/outages/999999")

    assert response.status_code == 404
