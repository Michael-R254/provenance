import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from ingest.migrate import apply_migrations

FIXTURES = Path(__file__).parent / "fixtures" / "content"
MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"


@pytest.fixture
def fixture_content() -> Path:
    return FIXTURES


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    """A freshly migrated database. Wipes the target database's public schema: use a test DB."""
    url = os.environ.get("PROVENANCE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PROVENANCE_TEST_DATABASE_URL is not set")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        apply_migrations(conn, MIGRATIONS)
        yield conn
