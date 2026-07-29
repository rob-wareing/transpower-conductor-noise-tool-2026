from transpower_conductor_noise_tool_2026.backend.app import create_app


def _make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app.test_client()


def test_login_with_valid_credentials_sets_session(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/auth/login",
        json={"email": "demo@transpower.example", "password": "demo-password"},
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "demo@transpower.example"


def test_login_with_invalid_credentials_is_rejected(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/auth/login",
        json={"email": "demo@transpower.example", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_me_requires_a_session(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_user_after_login(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)
    client.post(
        "/api/auth/login",
        json={"email": "demo@transpower.example", "password": "demo-password"},
    )

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "demo@transpower.example"


def test_logout_clears_the_session(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)
    client.post(
        "/api/auth/login",
        json={"email": "demo@transpower.example", "password": "demo-password"},
    )

    logout_response = client.post("/api/auth/logout")
    me_response = client.get("/api/auth/me")

    assert logout_response.status_code == 200
    assert me_response.status_code == 401
