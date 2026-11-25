import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from provenance.embedding import FakeEmbedder

MIGRATIONS = Path(__file__).resolve().parents[3] / "db" / "migrations"


def _vector(text: str) -> str:
    return "[" + ",".join(str(v) for v in FakeEmbedder().embed([text])[0]) + "]"


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    """A freshly migrated database. Wipes the target's public schema: use a throwaway DB."""
    url = os.environ.get("PROVENANCE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PROVENANCE_TEST_DATABASE_URL is not set")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))
        yield conn


def add_version(conn: psycopg.Connection, status: str, model: str = "fake-hash-bow") -> int:
    row = conn.execute(
        "INSERT INTO index_versions (embedding_model, chunker_version, status)"
        " VALUES (%s, '1', %s) RETURNING id",
        (model, status),
    ).fetchone()
    assert row is not None
    return int(row[0])


def add_document(
    conn: psycopg.Connection, version: int, slug: str, sections: dict[str, str]
) -> None:
    """Insert one fictional project document with one chunk per section."""
    row = conn.execute(
        "INSERT INTO documents (index_version, project_slug, title, doc_type, source_path, url,"
        " version, content_hash) VALUES (%s, %s, %s, 'project', %s, %s, 1, 'x') RETURNING id",
        (version, slug, slug.replace("-", " ").title(), f"projects/{slug}.md", f"/projects/{slug}"),
    ).fetchone()
    assert row is not None
    for ordinal, (section, text) in enumerate(sections.items()):
        conn.execute(
            "INSERT INTO chunks (index_version, document_id, section, anchor, ordinal, text,"
            " token_count, embedding) VALUES (%s, %s, %s, %s, %s, %s, 10, %s::vector)",
            (
                version,
                row[0],
                section,
                section.lower().replace(" ", "-"),
                ordinal,
                text,
                _vector(f"{section} {text}"),
            ),
        )


def add_project(
    conn: psycopg.Connection, version: int, slug: str, guardrails: list[str] | None = None
) -> None:
    import json

    conn.execute(
        "INSERT INTO projects (index_version, slug, title, summary, type, guardrails)"
        " VALUES (%s, %s, %s, 'A fictional project.', 'personal', %s)",
        (version, slug, slug.replace("-", " ").title(), json.dumps(guardrails or [])),
    )
