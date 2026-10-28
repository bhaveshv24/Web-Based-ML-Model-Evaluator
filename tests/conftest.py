"""Shared pytest configuration."""

import pytest


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix, tmp_path_factory):
    """Use a file-backed SQLite test database instead of the shared-cache in-memory default.

    tests/test_async_e2e.py runs a real Celery worker in threads next to the test client.
    In shared-cache in-memory mode SQLite reports "database table is locked" to concurrent
    connections immediately instead of waiting, which made that test flaky. A file database
    uses normal locking with a busy timeout. Production uses PostgreSQL either way.
    """
    from django.conf import settings

    database = settings.DATABASES["default"]
    if database["ENGINE"].endswith("sqlite3"):
        database.setdefault("TEST", {})["NAME"] = str(
            tmp_path_factory.mktemp("db") / "test.sqlite3"
        )
        database.setdefault("OPTIONS", {})["timeout"] = 30
