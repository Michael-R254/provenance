"""Write a new index version and switch the active version.

The public API reads only the active version, so a new index can be built beside the live
one and switched over in a single transaction. The previous version is kept for rollback.
"""

import json
from collections.abc import Sequence

import psycopg

from ingest import CHUNKER_VERSION
from ingest.embed import Embedder, embedding_input
from ingest.schema import ProjectFrontmatter
from ingest.validate import PreparedDocument


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in vector) + "]"


def build_index(
    conn: psycopg.Connection,
    documents: Sequence[PreparedDocument],
    embedder: Embedder,
    git_sha: str | None = None,
) -> int:
    """Insert a complete index version with status 'building'. Returns its id."""
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO index_versions (git_sha, embedding_model, chunker_version)"
            " VALUES (%s, %s, %s) RETURNING id",
            (git_sha, embedder.model_name, CHUNKER_VERSION),
        ).fetchone()
        if row is None:
            raise RuntimeError("could not create an index version")
        version_id: int = row[0]

        for doc in documents:
            meta = doc.meta
            project_slug = meta.id if isinstance(meta, ProjectFrontmatter) else None
            if isinstance(meta, ProjectFrontmatter):
                conn.execute(
                    "INSERT INTO projects (index_version, slug, title, summary, type, period,"
                    " repo_url, tags, guardrails) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        version_id,
                        meta.id,
                        meta.title,
                        meta.summary,
                        meta.type,
                        meta.period,
                        meta.repo,
                        json.dumps(meta.tags()),
                        json.dumps(meta.guardrails),
                    ),
                )
            doc_row = conn.execute(
                "INSERT INTO documents (index_version, project_slug, title, doc_type, source_path,"
                " url, version, content_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                " RETURNING id",
                (
                    version_id,
                    project_slug,
                    meta.title,
                    doc.source.doc_type,
                    doc.source.relative_path,
                    doc.url,
                    meta.version,
                    doc.source.content_hash,
                ),
            ).fetchone()
            if doc_row is None:
                raise RuntimeError(f"could not insert document {doc.source.relative_path}")
            vectors = embedder.embed(
                [embedding_input(meta.title, c.section, c.text) for c in doc.chunks]
            )
            for chunk, vector in zip(doc.chunks, vectors, strict=True):
                conn.execute(
                    "INSERT INTO chunks (index_version, document_id, section, anchor, ordinal,"
                    " text, token_count, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        version_id,
                        doc_row[0],
                        chunk.section,
                        chunk.anchor,
                        chunk.ordinal,
                        chunk.text,
                        chunk.token_count,
                        _vector_literal(vector),
                    ),
                )
    return version_id


def activate(conn: psycopg.Connection, version_id: int) -> None:
    """Make version_id the only active version; the previous active one becomes retired."""
    with conn.transaction():
        status = conn.execute(
            "SELECT status FROM index_versions WHERE id = %s FOR UPDATE", (version_id,)
        ).fetchone()
        if status is None:
            raise ValueError(f"index version {version_id} does not exist")
        if status[0] not in ("building", "retired"):
            raise ValueError(f"index version {version_id} cannot be activated from {status[0]}")
        conn.execute("UPDATE index_versions SET status = 'retired' WHERE status = 'active'")
        conn.execute(
            "UPDATE index_versions SET status = 'active', activated_at = now() WHERE id = %s",
            (version_id,),
        )


def mark_failed(conn: psycopg.Connection, version_id: int) -> None:
    with conn.transaction():
        conn.execute(
            "UPDATE index_versions SET status = 'failed' WHERE id = %s AND status = 'building'",
            (version_id,),
        )


def active_version(conn: psycopg.Connection) -> int | None:
    row = conn.execute("SELECT id FROM index_versions WHERE status = 'active'").fetchone()
    return None if row is None else int(row[0])


def check_version(
    conn: psycopg.Connection,
    version_id: int,
    documents: Sequence[PreparedDocument],
    embedding_model: str,
) -> list[str]:
    """Structural checks on a built version before activation. Returns problems (empty if none).

    Confirms the version holds exactly the approved documents it was built from, each with all
    of its chunks, and that it was embedded with the model the API queries with.
    """
    row = conn.execute(
        "SELECT status, embedding_model FROM index_versions WHERE id = %s", (version_id,)
    ).fetchone()
    if row is None:
        return [f"index version {version_id} does not exist"]
    problems = []
    if row[0] != "building":
        problems.append(f"status is {row[0]}, expected building")
    if row[1] != embedding_model:
        problems.append(f"embedded with {row[1]!r}, expected {embedding_model!r}")

    expected = {doc.source.relative_path: len(doc.chunks) for doc in documents}
    stored: dict[str, int] = dict(
        conn.execute(
            "SELECT d.source_path, count(c.id) FROM documents d"
            " LEFT JOIN chunks c ON c.document_id = d.id"
            " WHERE d.index_version = %s GROUP BY d.source_path",
            (version_id,),
        ).fetchall()
    )
    if not expected:
        problems.append("no approved documents to compare against")
    for path in sorted(expected.keys() - stored.keys()):
        problems.append(f"missing document {path}")
    for path in sorted(stored.keys() - expected.keys()):
        problems.append(f"unexpected document {path}")
    for path in sorted(expected.keys() & stored.keys()):
        if stored[path] != expected[path]:
            problems.append(f"{path} has {stored[path]} chunk(s), expected {expected[path]}")

    projects = {doc.meta.id for doc in documents if isinstance(doc.meta, ProjectFrontmatter)}
    stored_projects = {
        r[0]
        for r in conn.execute(
            "SELECT slug FROM projects WHERE index_version = %s", (version_id,)
        ).fetchall()
    }
    if projects != stored_projects:
        problems.append("project rows do not match the approved project files")
    return problems


def list_versions(conn: psycopg.Connection, limit: int = 10) -> list[tuple[object, ...]]:
    """Recent versions, newest first: id, status, created, activated, git sha, chunk count."""
    return conn.execute(
        "SELECT v.id, v.status, v.created_at, v.activated_at, v.git_sha,"
        " (SELECT count(*) FROM chunks c WHERE c.index_version = v.id)"
        " FROM index_versions v ORDER BY v.id DESC LIMIT %s",
        (limit,),
    ).fetchall()
