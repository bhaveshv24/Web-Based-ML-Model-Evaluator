"""TSMP-21 (MLE-21) SEC-009: secrets, transport security, CORS and dependency scanning.

SEC-009: "Secrets shall be supplied through environment variables, never committed; production
traffic shall use HTTPS and a restrictive CORS policy; dependencies shall be scanned."
The SRS method is "configuration review + scan". These tests automate the review part.

Each settings case imports `config.settings` in a fresh interpreter, so the module-level
environment handling runs exactly as it does at start-up.
The HTTPS case is a strict xfail for DEF-09 (open). It turns into an XPASS failure once the
settings exist, so the fix is noticed.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from rest_framework.test import APIClient

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_ENV = ("DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DJANGO_SETTINGS_MODULE", "DJANGO_HTTPS")
SECRET_NAME = re.compile(r"SECRET|PASSWORD|TOKEN|API_KEY", re.IGNORECASE)


def load_settings(**env):
    """Import config.settings in a new process with exactly the given settings variables."""
    clean = {key: value for key, value in os.environ.items() if key not in SETTINGS_ENV}
    clean.update(env, PYTHONPATH=str(ROOT / "backend"), DJANGO_SETTINGS_MODULE="config.settings")
    code = (
        "import json; from config import settings as s; print(json.dumps({"
        "'SECRET_KEY': s.SECRET_KEY, 'DEBUG': s.DEBUG,"
        "'SESSION_COOKIE_SECURE': s.SESSION_COOKIE_SECURE,"
        "'CSRF_COOKIE_SECURE': s.CSRF_COOKIE_SECURE,"
        "'SECURE_SSL_REDIRECT': getattr(s, 'SECURE_SSL_REDIRECT', False),"
        "'SECURE_HSTS_SECONDS': getattr(s, 'SECURE_HSTS_SECONDS', 0),"
        "'SECURE_PROXY_SSL_HEADER': getattr(s, 'SECURE_PROXY_SSL_HEADER', None),"
        "'INSTALLED_APPS': s.INSTALLED_APPS, 'MIDDLEWARE': s.MIDDLEWARE}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], env=clean, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def env_file_values(path):
    pairs = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            pairs[key.strip()] = value.strip()
    return pairs


# ------------------------------------------------------------------------- secrets via env


def test_secret_key_is_read_from_the_environment():
    supplied = "env-supplied-" + os.urandom(8).hex()
    assert load_settings(DJANGO_SECRET_KEY=supplied)["SECRET_KEY"] == supplied


def test_without_an_environment_key_each_process_gets_a_fresh_random_key():
    first, second = load_settings()["SECRET_KEY"], load_settings()["SECRET_KEY"]
    assert first != second and len(first) >= 50
    placeholder = env_file_values(ROOT / ".env.example")["DJANGO_SECRET_KEY"]
    assert placeholder not in (first, second)


def test_env_example_holds_placeholders_only():
    values = env_file_values(ROOT / ".env.example")
    secrets_ = {key: value for key, value in values.items() if SECRET_NAME.search(key)}
    assert secrets_, "expected DJANGO_SECRET_KEY and POSTGRES_PASSWORD in .env.example"
    for key, value in secrets_.items():
        assert value.startswith("replace-with-"), f"{key} looks like a real value"


def test_compose_takes_every_secret_from_the_environment():
    compose = (ROOT / "docker-compose.yml").read_text()
    assigned = re.findall(r"^\s*([A-Z_]+):\s*(.+?)\s*$", compose, re.MULTILINE)
    secrets_ = [(key, value) for key, value in assigned if SECRET_NAME.search(key)]
    assert secrets_
    for key, value in secrets_:
        assert value.startswith("${"), f"{key} is hard-coded in docker-compose.yml"
    # Compose refuses to start without a secret key instead of falling back to a default.
    assert "${DJANGO_SECRET_KEY:?" in compose


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a Git checkout"
)
def test_env_file_is_ignored_and_not_tracked():
    run = lambda *args: subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: E731
    assert run("check-ignore", "-q", ".env").returncode == 0
    tracked = run("ls-files").stdout.splitlines()
    assert not [p for p in tracked if Path(p).name == ".env" or Path(p).suffix in {".pem", ".key"}]


# ---------------------------------------------------------------------- production defaults


def test_debug_is_off_by_default_and_cookies_are_secure():
    production = load_settings(DJANGO_SECRET_KEY="x" * 50)
    assert production["DEBUG"] is False
    assert production["SESSION_COOKIE_SECURE"] and production["CSRF_COOKIE_SECURE"]
    development = load_settings(DJANGO_SECRET_KEY="x" * 50, DJANGO_DEBUG="1")
    assert development["DEBUG"] is True and not development["SESSION_COOKIE_SECURE"]


def test_production_settings_enforce_https():
    production = load_settings(DJANGO_SECRET_KEY="x" * 50, DJANGO_HTTPS="1")
    assert production["SECURE_SSL_REDIRECT"] is True
    assert production["SECURE_HSTS_SECONDS"] > 0
    assert production["SECURE_PROXY_SSL_HEADER"] is not None


# --------------------------------------------------------------------------------- CORS


def test_no_cors_middleware_is_installed():
    configured = load_settings(DJANGO_SECRET_KEY="x" * 50)
    assert not any("cors" in app.lower() for app in configured["INSTALLED_APPS"])
    assert not any("cors" in layer.lower() for layer in configured["MIDDLEWARE"])


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["options", "post"])
@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/evaluations"])
def test_cross_origin_requests_get_no_cors_grant(method, path):
    client = APIClient()
    response = getattr(client, method)(
        path,
        {},
        format="json",
        HTTP_ORIGIN="https://attacker.example",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )
    granted = {k.lower() for k in response.headers if k.lower().startswith("access-control-")}
    assert granted == set(), f"{method.upper()} {path} sent {granted}"


# ---------------------------------------------------------------------- dependency scanning


def test_ci_scans_project_and_sandbox_dependencies_on_every_push():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert re.search(r"^on:\s*\n(?:\s+.*\n)*?\s+push:", workflow, re.MULTILINE)
    assert "pip-audit --skip-editable" in workflow
    assert "pip-audit -r sandbox/requirements.txt" in workflow
    assert re.search(r"bandit .*-ll", workflow)
