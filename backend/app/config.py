"""Settings, read from environment variables.

Local development needs none of them. In production (APP_ENV=production) the app refuses to start without
a proper SECRET_KEY, serves cookies over HTTPS only, and turns off the API docs and CORS.
"""
import os
import secrets
import warnings
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

# Where the database and cached files live. Outside OneDrive on purpose: a live SQLite file inside a
# synced folder can get corrupted. Override with STOCKWATCHER_DATA (the Docker image uses /data).
DATA_DIR = Path(os.environ.get("STOCKWATCHER_DATA") or (Path.home() / "StockWatcherData"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "stockwatcher.db"

if "onedrive" in str(DATA_DIR).lower():
    warnings.warn(f"Data folder {DATA_DIR} looks like it is inside OneDrive. "
                  "Set STOCKWATCHER_DATA to a folder outside it to avoid database corruption.")

COOKIE_SECURE = _flag("COOKIE_SECURE", IS_PRODUCTION)   # send the login cookie over HTTPS only
ENABLE_DOCS = _flag("ENABLE_DOCS", not IS_PRODUCTION)   # the interactive API docs at /docs
STATIC_DIR = Path(os.environ["STATIC_DIR"]) if os.environ.get("STATIC_DIR") else None  # the built frontend

# Browsers on these origins may call state-changing endpoints in addition to the site's own address.
ALLOWED_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}
if not IS_PRODUCTION:
    ALLOWED_ORIGINS |= {"http://localhost:5173", "http://127.0.0.1:5173"}


def _load_secret_key() -> str:
    """The key that signs login cookies."""
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        if IS_PRODUCTION and len(key) < 32:
            raise RuntimeError("SECRET_KEY is too short. In production it must be at least 32 characters. "
                               "Make one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
        return key
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY is not set. In production it must be provided as an environment variable. "
                           "Make one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
    key_file = DATA_DIR / "secret.key"  # development only: generated once and kept locally
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


SECRET_KEY = _load_secret_key()
