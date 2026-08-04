from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.site import Site


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


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True})


def test_ignored_site_excluded_from_sites_endpoint(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        site = Site.query.filter_by(noise_site_id=51).first()
        site.is_ignored = True
        db.session.commit()

    client = app.test_client()
    response = client.get("/api/sites")

    ids = {item["noise_site_id"] for item in response.get_json()["items"]}
    assert 51 not in ids


def test_ignored_site_excluded_from_sites_detail_by_default_but_included_on_request(
    tmp_path, monkeypatch
):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        site = Site.query.filter_by(noise_site_id=51).first()
        site.is_ignored = True
        db.session.commit()

    client = app.test_client()

    default_response = client.get("/api/sites/detail")
    default_ids = {item["noise_site_id"] for item in default_response.get_json()["items"]}
    assert 51 not in default_ids

    include_response = client.get("/api/sites/detail?include_ignored=true")
    include_ids = {item["noise_site_id"] for item in include_response.get_json()["items"]}
    assert 51 in include_ids
    site_payload = next(
        item for item in include_response.get_json()["items"] if item["noise_site_id"] == 51
    )
    assert site_payload["is_ignored"] is True
