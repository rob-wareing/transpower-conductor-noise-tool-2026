from transpower_conductor_noise_tool_2026.backend.app import create_app


def test_sites_endpoint_returns_seeded_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})

    client = app.test_client()
    response = client.get("/api/sites")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] > 0
    assert payload["items"][0]["noise_site_id"] == 51
    assert payload["items"][0]["site_name"] == "Demo Site"
