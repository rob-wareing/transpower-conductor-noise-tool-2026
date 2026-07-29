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


def test_historical_endpoint_returns_seeded_rows(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/historical")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] > 0
    assert {"noise_site_id", "period_end_date", "leq_adj", "tone_100hz"} <= set(
        payload["items"][0].keys()
    )


def test_create_historical_result_requires_authentication(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/historical",
        json={"noise_site_id": 51, "period_end_date": "2025-01-01"},
    )

    assert response.status_code == 401


def test_create_historical_result_with_write_access_persists(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/api/historical",
        json={
            "noise_site_id": 51,
            "period_end_date": "2025-06-01",
            "leq_adj": 48.5,
            "tone_100hz": 10.4,
        },
    )

    assert response.status_code == 201
    result = response.get_json()["result"]
    assert result["period_length"] == 2
    assert result["leq_adj"] == 48.5

    list_response = client.get("/api/historical")
    assert any(item["id"] == result["id"] for item in list_response.get_json()["items"])


def test_create_historical_result_unknown_site_returns_400(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/api/historical",
        json={"noise_site_id": 999999, "period_end_date": "2025-06-01"},
    )

    assert response.status_code == 400


def test_update_historical_result_requires_write_access(tmp_path, monkeypatch):
    from transpower_conductor_noise_tool_2026.backend.domain.auth_service import create_user

    app, client = _make_client(tmp_path, monkeypatch)
    with app.app_context():
        create_user("Read Only", "readonly@transpower.example", "password", write_access=False)
    client.post(
        "/api/auth/login", json={"email": "readonly@transpower.example", "password": "password"}
    )

    response = client.patch("/api/historical/1", json={"leq_adj": 50.0})

    assert response.status_code == 403


def test_update_historical_result_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/historical/999999", json={"leq_adj": 50.0})

    assert response.status_code == 404


def test_delete_historical_result_removes_it(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    create_response = client.post(
        "/api/historical",
        json={"noise_site_id": 51, "period_end_date": "2025-07-01"},
    )
    result_id = create_response.get_json()["result"]["id"]

    delete_response = client.delete(f"/api/historical/{result_id}")
    assert delete_response.status_code == 200

    list_response = client.get("/api/historical")
    assert all(item["id"] != result_id for item in list_response.get_json()["items"])


def test_delete_historical_result_returns_404_for_unknown_id(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.delete("/api/historical/999999")

    assert response.status_code == 404
