from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.grease_description import (
    GreaseDescription,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.grease_description_repository import (
    GreaseDescriptionRepository,
)


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return create_app({"TESTING": True, "AUTO_SEED_DATA": False})


def test_list_all_returns_rows_ordered_by_grease(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        db.session.add(GreaseDescription(grease="C2", description="Fully greased"))
        db.session.add(GreaseDescription(grease="C1", description="Steel core greased only"))
        db.session.commit()

        rows = GreaseDescriptionRepository().list_all()

        assert [row.grease for row in rows] == ["C1", "C2"]


def test_add_all_persists_records(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.app_context():
        GreaseDescriptionRepository().add_all(
            [
                GreaseDescription(grease="C1", description="Steel core greased only"),
                GreaseDescription(grease="C1.5", description="1 layer of Al greased"),
            ]
        )

        rows = GreaseDescriptionRepository().list_all()

        assert {row.grease: row.description for row in rows} == {
            "C1": "Steel core greased only",
            "C1.5": "1 layer of Al greased",
        }
