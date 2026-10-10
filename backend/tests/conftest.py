"""Test setup. The app reads its settings when it is imported, so the environment is prepared first.
Tests run in production mode, which is the configuration that matters (HTTPS-only cookies, no docs, no CORS)."""
import os
import sys
import tempfile
import types
import uuid
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="stockwatcher-tests-"))
_static = _tmp / "static"
(_static / "assets").mkdir(parents=True)
(_static / "index.html").write_text("<!doctype html><title>test app</title><div id='root'></div>")
(_static / "assets" / "app.js").write_text("console.log('hi')")
(_static / "theme-init.js").write_text("// theme")
os.environ.update({
    "APP_ENV": "production",
    "SECRET_KEY": "test-secret-key-" + "x" * 48,
    "STOCKWATCHER_DATA": str(_tmp / "data"),
    "STATIC_DIR": str(_static),
    "ENABLE_DOCS": "false",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import yfinance  # noqa: F401
except ImportError:  # lets the tests run on a machine without the data library; nothing here touches the network
    sys.modules["yfinance"] = types.ModuleType("yfinance")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ratelimit  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

init_db()
PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def _clean_rate_limits():
    ratelimit.reset_all()
    yield


@pytest.fixture
def fresh_client():
    """A new browser with no cookies. HTTPS, because the login cookie is HTTPS-only."""
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def make_user():
    def make(prefix: str = "user", password: str = PASSWORD) -> str:
        name = f"{prefix}-{uuid.uuid4().hex[:8]}"
        with SessionLocal() as db:
            db.add(User(username=name, password_hash=hash_password(password)))
            db.commit()
        return name
    return make


@pytest.fixture
def logged_in(make_user, fresh_client):
    """Factory: a logged-in client for a brand-new user."""
    def build(prefix: str = "user"):
        name = make_user(prefix)
        client = TestClient(app, base_url="https://testserver")
        assert client.post("/api/auth/login", json={"username": name, "password": PASSWORD}).status_code == 200
        return client, name
    return build
