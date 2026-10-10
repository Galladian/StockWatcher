import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def run(changes: dict, remove=()):
    env = {k: v for k, v in os.environ.items() if k not in remove}
    env.update(changes)
    code = "import app.config as c; print(c.COOKIE_SECURE, c.ENABLE_DOCS)"
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True)


def test_production_refuses_to_start_without_a_secret(tmp_path):
    r = run({"APP_ENV": "production", "STOCKWATCHER_DATA": str(tmp_path)}, remove=("SECRET_KEY",))
    assert r.returncode != 0 and "SECRET_KEY is not set" in r.stderr


def test_production_rejects_a_short_secret(tmp_path):
    r = run({"APP_ENV": "production", "STOCKWATCHER_DATA": str(tmp_path), "SECRET_KEY": "too-short"})
    assert r.returncode != 0 and "too short" in r.stderr


def test_production_defaults_are_the_safe_ones(tmp_path):
    r = run({"APP_ENV": "production", "STOCKWATCHER_DATA": str(tmp_path), "SECRET_KEY": "k" * 64}, remove=("ENABLE_DOCS",))
    assert r.returncode == 0 and r.stdout.split() == ["True", "False"]  # secure cookies on, docs off


def test_development_needs_no_configuration(tmp_path):
    r = run({"APP_ENV": "development", "STOCKWATCHER_DATA": str(tmp_path)}, remove=("SECRET_KEY", "ENABLE_DOCS", "COOKIE_SECURE"))
    assert r.returncode == 0 and r.stdout.split() == ["False", "True"]
    assert (tmp_path / "secret.key").exists()
