from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "transpower_conductor_noise_tool_2026.db"
DEFAULT_SITE_FIXTURE_PATH = ROOT_DIR / "data" / "site.csv"
DEFAULT_USER_FIXTURE_PATH = ROOT_DIR / "data" / "user.csv"
DEFAULT_PROCESSED_READING_FIXTURE_PATH = ROOT_DIR / "data" / "processed_reading.csv"
DEFAULT_OUTAGE_TYPE_FIXTURE_PATH = ROOT_DIR / "data" / "outage_type.csv"
DEFAULT_OUTAGE_FIXTURE_PATH = ROOT_DIR / "data" / "outage.csv"
DEFAULT_RECONDUCTORING_FIXTURE_PATH = ROOT_DIR / "data" / "reconductoring.csv"
DEFAULT_HISTORICAL_RESULT_FIXTURE_PATH = ROOT_DIR / "data" / "historical_result.csv"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int_list(name: str) -> list[int] | None:
    value = os.environ.get(name)
    if not value:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


class Settings:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SITE_FIXTURE_PATH = Path(os.environ.get("SITE_FIXTURE_PATH", DEFAULT_SITE_FIXTURE_PATH))
    USER_FIXTURE_PATH = Path(os.environ.get("USER_FIXTURE_PATH", DEFAULT_USER_FIXTURE_PATH))
    PROCESSED_READING_FIXTURE_PATH = Path(
        os.environ.get("PROCESSED_READING_FIXTURE_PATH", DEFAULT_PROCESSED_READING_FIXTURE_PATH)
    )
    OUTAGE_TYPE_FIXTURE_PATH = Path(
        os.environ.get("OUTAGE_TYPE_FIXTURE_PATH", DEFAULT_OUTAGE_TYPE_FIXTURE_PATH)
    )
    OUTAGE_FIXTURE_PATH = Path(os.environ.get("OUTAGE_FIXTURE_PATH", DEFAULT_OUTAGE_FIXTURE_PATH))
    RECONDUCTORING_FIXTURE_PATH = Path(
        os.environ.get("RECONDUCTORING_FIXTURE_PATH", DEFAULT_RECONDUCTORING_FIXTURE_PATH)
    )
    HISTORICAL_RESULT_FIXTURE_PATH = Path(
        os.environ.get("HISTORICAL_RESULT_FIXTURE_PATH", DEFAULT_HISTORICAL_RESULT_FIXTURE_PATH)
    )
    AUTO_INIT_DB = _env_bool("AUTO_INIT_DB", True)
    AUTO_SEED_DATA = _env_bool("AUTO_SEED_DATA", True)
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    NW_BASE_URL = os.environ.get("NW_BASE_URL", "https://api.noiseandweather.com/v1")
    NW_USERNAME = os.environ.get("NW_USERNAME")
    NW_PASSWORD = os.environ.get("NW_PASSWORD")
    NW_REQUEST_TIMEOUT = float(os.environ.get("NW_REQUEST_TIMEOUT", "30"))
    INGEST_SITE_IDS = _env_int_list("INGEST_SITE_IDS")
