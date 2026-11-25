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
