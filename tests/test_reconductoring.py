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


def test_reconductoring_endpoint_returns_seeded_rows(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/reconductoring")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] > 0
    assert {"noise_site_id", "conductor_and_treatment", "reconductoring_date"} <= set(
        payload["items"][0].keys()
    )


def test_create_reconductoring_event_requires_authentication(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/reconductoring",
        json={"noise_site_id": 51, "reconductoring_date": "2025-01-01"},
    )

    assert response.status_code == 401


def test_create_reconductoring_event_with_write_access_persists(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/api/reconductoring",
        json={
            "noise_site_id": 51,
            "conductor_and_treatment": "New conductor",
            "grease": "test-grease",
            "reconductoring_date": "2025-06-01",
            "notes": "Test event",
        },
    )

    assert response.status_code == 201
    event = response.get_json()["event"]
    assert event["conductor_and_treatment"] == "New conductor"

    list_response = client.get("/api/reconductoring")
    assert any(item["id"] == event["id"] for item in list_response.get_json()["items"])


def test_update_reconductoring_event_requires_write_access(tmp_path, monkeypatch):
    from transpower_conductor_noise_tool_2026.backend.domain.auth_service import create_user

    app, client = _make_client(tmp_path, monkeypatch)
    with app.app_context():
        create_user("Read Only", "readonly@transpower.example", "password", write_access=False)
    client.post(
        "/api/auth/login", json={"email": "readonly@transpower.example", "password": "password"}
    )

    response = client.patch("/api/reconductoring/1", json={"notes": "hacked"})

    assert response.status_code == 403


def test_update_reconductoring_event_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/reconductoring/999999", json={"notes": "x"})

    assert response.status_code == 404


def test_delete_reconductoring_event_removes_it(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    create_response = client.post(
        "/api/reconductoring",
        json={"noise_site_id": 51, "reconductoring_date": "2025-07-01"},
    )
    event_id = create_response.get_json()["event"]["id"]

    delete_response = client.delete(f"/api/reconductoring/{event_id}")
    assert delete_response.status_code == 200

    list_response = client.get("/api/reconductoring")
    assert all(item["id"] != event_id for item in list_response.get_json()["items"])


def test_delete_reconductoring_event_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.delete("/api/reconductoring/999999")

    assert response.status_code == 404
