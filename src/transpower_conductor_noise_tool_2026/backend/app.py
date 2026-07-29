import os

from flask import Flask, jsonify

from transpower_conductor_noise_tool_2026.backend.config import DEFAULT_DB_PATH, Settings
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence import models  # noqa: F401
from transpower_conductor_noise_tool_2026.backend.persistence.seed import (
    seed_historical_results_from_csv,
    seed_outage_types_from_csv,
    seed_outages_from_csv,
    seed_processed_readings_from_csv,
    seed_reconductoring_from_csv,
    seed_sites_from_csv,
    seed_users_from_csv,
)

from .api.auth_routes import bp as auth_bp
from .api.chart_routes import bp as chart_bp
from .api.historical_routes import bp as historical_bp
from .api.outage_routes import bp as outage_bp
from .api.reconductoring_routes import bp as reconductoring_bp
from .api.routes import bp as api_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Settings)
    # Settings.SQLALCHEMY_DATABASE_URI is a class attribute evaluated once at import
    # time, so a DATABASE_URL set via monkeypatch/env *after* Settings has already
    # been imported elsewhere in the process would otherwise be silently ignored.
    # Re-read it fresh here so each create_app() call honours the current env.
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}"
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chart_bp)
    app.register_blueprint(outage_bp)
    app.register_blueprint(reconductoring_bp)
    app.register_blueprint(historical_bp)

    with app.app_context():
        if app.config.get("AUTO_INIT_DB", False):
            db.create_all()
        if app.config.get("AUTO_SEED_DATA", False):
            seed_sites_from_csv(app.config["SITE_FIXTURE_PATH"])
            seed_users_from_csv(app.config["USER_FIXTURE_PATH"])
            seed_processed_readings_from_csv(app.config["PROCESSED_READING_FIXTURE_PATH"])
            seed_outage_types_from_csv(app.config["OUTAGE_TYPE_FIXTURE_PATH"])
            seed_outages_from_csv(app.config["OUTAGE_FIXTURE_PATH"])
            seed_reconductoring_from_csv(app.config["RECONDUCTORING_FIXTURE_PATH"])
            seed_historical_results_from_csv(app.config["HISTORICAL_RESULT_FIXTURE_PATH"])

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "backend"})

    return app
