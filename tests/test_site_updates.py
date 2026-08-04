from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain.auth_service import create_user


def _make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    return app, app.test_client()


def _login(client, email="demo@transpower.example", password="demo-password"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def test_sites_detail_endpoint_returns_full_fields(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/sites/detail")

    assert response.status_code == 200
    payload = response.get_json()
    site = next(item for item in payload["items"] if item["noise_site_id"] == 51)
    assert set(site.keys()) == {
        "noise_site_id",
        "site_name",
        "site_code",
        "plot_color",
        "height_adj_db",
        "data_folder",
        "report_folder",
        "latitude",
        "longitude",
        "is_ignored",
    }


def test_update_site_requires_authentication(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)

    response = client.patch("/api/sites/51", json={"site_code": "NEW"})

    assert response.status_code == 401


def test_update_site_requires_write_access(tmp_path, monkeypatch):
    app, client = _make_client(tmp_path, monkeypatch)
    with app.app_context():
        create_user("Read Only", "readonly@transpower.example", "password", write_access=False)
    _login(client, "readonly@transpower.example", "password")

    response = client.patch("/api/sites/51", json={"site_code": "NEW"})

    assert response.status_code == 403


def test_update_site_with_write_access_persists_changes(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)  # seeded demo user has write_access=True

    response = client.patch(
        "/api/sites/51",
        json={"site_code": "NEW-CODE", "plot_color": "#ff00aa", "height_adj_db": 1.5},
    )

    assert response.status_code == 200
    site = response.get_json()["site"]
    assert site["site_code"] == "NEW-CODE"
    assert site["plot_color"] == "#ff00aa"
    assert site["height_adj_db"] == 1.5

    detail_response = client.get("/api/sites/detail")
    updated = next(
        item for item in detail_response.get_json()["items"] if item["noise_site_id"] == 51
    )
    assert updated["site_code"] == "NEW-CODE"


def test_update_site_rejects_invalid_plot_color(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/sites/51", json={"plot_color": "not-a-color"})

    assert response.status_code == 400


def test_update_site_persists_coordinates(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch(
        "/api/sites/51", json={"latitude": -40.3523, "longitude": 175.6082}
    )

    assert response.status_code == 200
    site = response.get_json()["site"]
    assert site["latitude"] == -40.3523
    assert site["longitude"] == 175.6082


def test_update_site_rejects_out_of_range_latitude(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/sites/51", json={"latitude": 200})

    assert response.status_code == 400


def test_update_site_rejects_out_of_range_longitude(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/sites/51", json={"longitude": -200})

    assert response.status_code == 400


def test_update_site_returns_404_for_unknown_site(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    response = client.patch("/api/sites/999999", json={"site_code": "X"})

    assert response.status_code == 404


def test_update_site_never_allows_editing_locked_fields(tmp_path, monkeypatch):
    _app, client = _make_client(tmp_path, monkeypatch)
    _login(client)

    # site_name/noise_site_id aren't part of SiteUpdate at all, so sending them
    # should simply be ignored rather than erroring or being applied.
    response = client.patch("/api/sites/51", json={"site_name": "Hacked Name"})

    assert response.status_code == 200
    site = response.get_json()["site"]
    assert site["site_name"] != "Hacked Name"
