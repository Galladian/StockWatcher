"""Where the database and secret key live.

Defaults to C:\\Users\\<you>\\StockWatcherData (outside OneDrive on purpose: a live
SQLite file inside a synced folder can get corrupted). Override with the
STOCKWATCHER_DATA environment variable.
"""
import os
import secrets
import warnings
from pathlib import Path

DATA_DIR = Path(os.environ.get("STOCKWATCHER_DATA") or (Path.home() / "StockWatcherData"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "stockwatcher.db"

if "onedrive" in str(DATA_DIR).lower():
    warnings.warn(f"Data folder {DATA_DIR} looks like it is inside OneDrive. "
                  "Set STOCKWATCHER_DATA to a folder outside it to avoid database corruption.")


def get_secret_key() -> str:
    """Key used to sign login cookies. Generated once and kept in the data folder."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    key_file = DATA_DIR / "secret.key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()
