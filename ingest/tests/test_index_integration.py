from pathlib import Path

import psycopg
import pytest

from ingest.embed import FakeEmbedder
from ingest.index import activate, active_version, build_index, mark_failed
from ingest.validate import prepare

pytestmark = pytest.mark.integration


def _status(conn: psycopg.Connection, version: int) -> str:
    row = conn.execute("SELECT status FROM index_versions WHERE id = %s", (version,)).fetchone()
    assert row is not None
    return str(row[0])


def test_build_writes_documents_chunks_and_metadata(
    db: psycopg.Connection, fixture_content: Path
) -> None:
    result = prepare(fixture_content)
    version = build_index(db, result.documents, FakeEmbedder(), git_sha="abc123")

    assert _status(db, version) == "building"
    docs = db.execute(
        "SELECT source_path, doc_type, url FROM documents WHERE index_version = %s ORDER BY 1",
        (version,),
    ).fetchall()
    assert docs == [
        ("profile.md", "profile", "/about#profile"),
        ("projects/example-project-a.md", "project", "/projects/example-project-a"),
    ]
    anchors = [
        r[0]
        for r in db.execute(
            "SELECT c.anchor FROM chunks c JOIN documents d ON d.id = c.document_id"
            " WHERE d.source_path = 'projects/example-project-a.md' ORDER BY c.ordinal"
        )
    ]
    assert anchors == ["overview", "problem", "my-contributions", "results", "results-1"]
    guardrails = db.execute(
        "SELECT guardrails FROM projects WHERE index_version = %s AND slug = 'example-project-a'",
        (version,),
    ).fetchone()
    assert guardrails is not None and len(guardrails[0]) == 1
    drafts = db.execute("SELECT count(*) FROM chunks WHERE text LIKE '%zebra-draft-marker%'")
    assert drafts.fetchone() == (0,)


def test_full_text_and_vector_columns_are_searchable(
    db: psycopg.Connection, fixture_content: Path
) -> None:
    version = build_index(db, prepare(fixture_content).documents, FakeEmbedder())
    hit = db.execute(
        "SELECT anchor FROM chunks WHERE index_version = %s"
        " AND tsv @@ websearch_to_tsquery('english', 'hue values')",
        (version,),
    ).fetchone()
    assert hit == ("my-contributions",)
    query = FakeEmbedder().embed(["imaginary widgets by colour"])[0]
    nearest = db.execute(
        "SELECT anchor FROM chunks WHERE index_version = %s"
        " ORDER BY embedding <=> %s::vector LIMIT 1",
        (version, "[" + ",".join(str(v) for v in query) + "]"),
    ).fetchone()
    assert nearest == ("overview",)


def test_rerun_creates_new_version_and_activation_retires_previous(
    db: psycopg.Connection, fixture_content: Path
) -> None:
    documents = prepare(fixture_content).documents
    first = build_index(db, documents, FakeEmbedder())
    activate(db, first)
    second = build_index(db, documents, FakeEmbedder())

    assert second != first
    assert active_version(db) == first
    activate(db, second)
    assert active_version(db) == second
    assert _status(db, first) == "retired"

    activate(db, first)  # rollback
    assert active_version(db) == first
    assert _status(db, second) == "retired"


def test_failed_versions_cannot_be_activated(db: psycopg.Connection, fixture_content: Path) -> None:
    version = build_index(db, prepare(fixture_content).documents, FakeEmbedder())
    mark_failed(db, version)
    with pytest.raises(ValueError, match="cannot be activated"):
        activate(db, version)
    assert active_version(db) is None


def test_only_one_version_can_be_active(db: psycopg.Connection) -> None:
    db.execute(
        "INSERT INTO index_versions (embedding_model, chunker_version, status)"
        " VALUES ('m', '1', 'active')"
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(
            "INSERT INTO index_versions (embedding_model, chunker_version, status)"
            " VALUES ('m', '1', 'active')"
        )
