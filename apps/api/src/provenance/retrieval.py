"""Hybrid retrieval: pgvector similarity + Postgres full-text, merged with reciprocal rank fusion.

Reads only the active index version, and refuses to run if that version was embedded with a
different model from the one used for queries.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

import psycopg

from provenance.embedding import Embedder

logger = logging.getLogger(__name__)

Method = Literal["hybrid", "vector", "keyword"]

DEFAULT_CANDIDATES = 20
DEFAULT_RRF_K = 60


class RetrievalError(RuntimeError):
    """Base class for retrieval failures that the API turns into safe messages."""


class NoActiveIndexError(RetrievalError):
    pass


class EmbeddingModelMismatchError(RetrievalError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_title: str
    project_slug: str | None
    source_path: str
    url: str
    section: str
    anchor: str
    text: str
    vector_rank: int | None = None
    vector_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None
    fused_score: float = 0.0

    @property
    def citation_url(self) -> str:
        return f"{self.url}#{self.anchor}" if "#" not in self.url else self.url


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    method: Method
    index_version: int
    chunks: list[RetrievedChunk]
    timings_ms: dict[str, float] = field(default_factory=dict)


_SELECT = "SELECT c.id, d.title, d.project_slug, d.source_path, d.url, c.section, c.anchor, c.text"


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in vector) + "]"


def _row_to_chunk(row: tuple[object, ...]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=int(row[0]),  # type: ignore[call-overload]
        document_title=str(row[1]),
        project_slug=None if row[2] is None else str(row[2]),
        source_path=str(row[3]),
        url=str(row[4]),
        section=str(row[5]),
        anchor=str(row[6]),
        text=str(row[7]),
    )


def active_index(conn: psycopg.Connection) -> tuple[int, str]:
    row = conn.execute(
        "SELECT id, embedding_model FROM index_versions WHERE status = 'active'"
    ).fetchone()
    if row is None:
        raise NoActiveIndexError("no active index version")
    return int(row[0]), str(row[1])


def vector_search(
    conn: psycopg.Connection,
    index_version: int,
    query_vector: Sequence[float],
    limit: int,
    project: str | None = None,
) -> list[RetrievedChunk]:
    literal = _vector_literal(query_vector)
    with conn.transaction():
        # Keep scanning the HNSW index until enough rows survive the version/project filter.
        conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        rows = conn.execute(
            f"{_SELECT}, 1 - (c.embedding <=> %(v)s::vector) AS score"
            " FROM chunks c JOIN documents d ON d.id = c.document_id"
            " WHERE c.index_version = %(version)s"
            " AND (%(project)s::text IS NULL OR d.project_slug = %(project)s)"
            " ORDER BY c.embedding <=> %(v)s::vector LIMIT %(limit)s",
            {"v": literal, "version": index_version, "project": project, "limit": limit},
        ).fetchall()
    return [
        replace(_row_to_chunk(row), vector_rank=rank, vector_score=float(row[8]))
        for rank, row in enumerate(rows, start=1)
    ]


def keyword_search(
    conn: psycopg.Connection,
    index_version: int,
    query: str,
    limit: int,
    project: str | None = None,
) -> list[RetrievedChunk]:
    rows = conn.execute(
        f"{_SELECT}, ts_rank_cd(c.tsv, query.q) AS score"
        " FROM chunks c JOIN documents d ON d.id = c.document_id,"
        # Match ANY query term (not all): natural-language questions rarely contain every
        # term of the passage that answers them. ts_rank_cd still favours chunks covering more.
        " (SELECT replace(plainto_tsquery('english', %(q)s)::text, '&', '|')::tsquery AS q) query"
        " WHERE c.index_version = %(version)s AND c.tsv @@ query.q"
        " AND (%(project)s::text IS NULL OR d.project_slug = %(project)s)"
        " ORDER BY score DESC, c.id LIMIT %(limit)s",
        {"q": query, "version": index_version, "project": project, "limit": limit},
    ).fetchall()
    return [
        replace(_row_to_chunk(row), keyword_rank=rank, keyword_score=float(row[8]))
        for rank, row in enumerate(rows, start=1)
    ]


def reciprocal_rank_fusion(
    vector_hits: Sequence[RetrievedChunk],
    keyword_hits: Sequence[RetrievedChunk],
    rrf_k: int = DEFAULT_RRF_K,
) -> list[RetrievedChunk]:
    """Merge two ranked lists. Each list contributes 1 / (rrf_k + rank) for every chunk it has.

    Ties are broken by best individual rank, then chunk id, so the order is deterministic.
    """
    merged: dict[int, RetrievedChunk] = {}
    for hit in vector_hits:
        merged[hit.chunk_id] = hit
    for hit in keyword_hits:
        existing = merged.get(hit.chunk_id)
        merged[hit.chunk_id] = (
            hit
            if existing is None
            else replace(existing, keyword_rank=hit.keyword_rank, keyword_score=hit.keyword_score)
        )

    def score(chunk: RetrievedChunk) -> float:
        total = 0.0
        if chunk.vector_rank is not None:
            total += 1.0 / (rrf_k + chunk.vector_rank)
        if chunk.keyword_rank is not None:
            total += 1.0 / (rrf_k + chunk.keyword_rank)
        return total

    def best_rank(chunk: RetrievedChunk) -> int:
        ranks = [r for r in (chunk.vector_rank, chunk.keyword_rank) if r is not None]
        return min(ranks)

    fused = [replace(c, fused_score=score(c)) for c in merged.values()]
    return sorted(fused, key=lambda c: (-c.fused_score, best_rank(c), c.chunk_id))


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        candidates: int = DEFAULT_CANDIDATES,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self.embedder = embedder
        self.candidates = candidates
        self.rrf_k = rrf_k

    def retrieve(
        self,
        conn: psycopg.Connection,
        query: str,
        top_n: int = 8,
        method: Method = "hybrid",
        project: str | None = None,
    ) -> RetrievalResult:
        timings: dict[str, float] = {}
        started = time.perf_counter()

        version, model = active_index(conn)
        if model != self.embedder.model_name:
            raise EmbeddingModelMismatchError(
                f"active index {version} uses {model!r}; queries use {self.embedder.model_name!r}"
            )

        vector_hits: list[RetrievedChunk] = []
        keyword_hits: list[RetrievedChunk] = []
        if method in ("hybrid", "vector"):
            t = time.perf_counter()
            query_vector = self.embedder.embed([query])[0]
            timings["embed"] = (time.perf_counter() - t) * 1000
            t = time.perf_counter()
            vector_hits = vector_search(conn, version, query_vector, self.candidates, project)
            timings["vector"] = (time.perf_counter() - t) * 1000
        if method in ("hybrid", "keyword"):
            t = time.perf_counter()
            keyword_hits = keyword_search(conn, version, query, self.candidates, project)
            timings["keyword"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        if method == "hybrid":
            ranked = reciprocal_rank_fusion(vector_hits, keyword_hits, self.rrf_k)
        elif method == "vector":
            ranked = reciprocal_rank_fusion(vector_hits, [], self.rrf_k)
        else:
            ranked = reciprocal_rank_fusion([], keyword_hits, self.rrf_k)
        timings["fuse"] = (time.perf_counter() - t) * 1000
        timings["total"] = (time.perf_counter() - started) * 1000

        result = RetrievalResult(
            query=query,
            method=method,
            index_version=version,
            chunks=ranked[:top_n],
            timings_ms={k: round(v, 2) for k, v in timings.items()},
        )
        logger.info(
            "retrieval",
            extra={
                "method": method,
                "index_version": version,
                "project": project,
                "results": len(result.chunks),
                "timings_ms": result.timings_ms,
            },
        )
        return result
