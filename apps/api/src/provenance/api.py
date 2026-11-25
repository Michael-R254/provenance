"""Public `/v1` endpoints: session, chat (server-sent events), sources and projects.

The API only reads the active index. It writes nothing but `query_logs` and `rate_limits`.
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from provenance import limits
from provenance.answering import (
    CitationFilter,
    Evidence,
    Turn,
    build_request,
    has_enough_evidence,
    retrieval_query,
    unsupported_sentences,
)
from provenance.config import Settings
from provenance.limits import Limit
from provenance.llm import GenerationResult, ProviderError
from provenance.prompts import answer_system_prompt
from provenance.retrieval import RetrievalError, RetrievalResult, active_index
from provenance.services import Database, Services
from provenance.sessions import InvalidSessionError, Session, hash_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1")

MESSAGES = {
    "invalid_session": "Your session has expired. Refresh the page to keep asking.",
    "rate_limited": "You're asking faster than the guide can keep up. Wait a minute and retry.",
    "spend_cap": "The guide is resting for today. Please come back tomorrow.",
    "input_too_long": "That question is too long. Please shorten it and try again.",
    "unavailable": "The guide couldn't answer just now. Please try again shortly.",
}
NO_EVIDENCE = (
    "I couldn't find anything in Michael's published write-ups that answers that. "
    "You could ask about one of the topics below instead."
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionRequest(Strict):
    turnstile_token: str = Field(min_length=1, max_length=2048)


class SessionResponse(BaseModel):
    session_token: str
    expires_at: int


class TurnIn(Strict):
    question: str = Field(max_length=2000)
    answer: str = Field(max_length=4000)


class ChatRequest(Strict):
    """Deliberately has no `role`: recruiter mode must never reach generation (AGENTS.md #6)."""

    question: str = Field(min_length=1, max_length=4000)
    history: list[TurnIn] = Field(default_factory=list, max_length=20)
    project: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,80}$")


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ServicesDep = Annotated[Services, Depends(get_services)]


def _database(services: Services) -> Database:
    if services.database is None:
        raise HTTPException(503, "unavailable")
    return services.database


def client_ip(request: Request) -> str:
    # Cloud Run's front end appends the caller's address to X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def _single_event(status: int, code: str) -> StreamingResponse:
    async def body() -> AsyncIterator[bytes]:
        yield _sse("error", {"code": code, "message": MESSAGES[code]})

    return _stream(body(), status)


def _stream(body: AsyncIterator[bytes], status: int = 200) -> StreamingResponse:
    return StreamingResponse(
        body,
        status_code=status,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(
    body: SessionRequest, request: Request, settings: SettingsDep, services: ServicesDep
) -> SessionResponse:
    database = _database(services)
    if services.signer is None:
        raise HTTPException(503, "unavailable")
    ip = client_ip(request)
    ip_key = hash_client(settings.ip_hash_salt.get_secret_value(), "ip", ip)
    sessions_limit = Limit("ip-sessions", 3600, settings.rate_ip_sessions_per_hour)

    def check_rate() -> bool:
        with database.connection() as conn:
            limits.purge_old_rate_limits(conn)
            return limits.hit(conn, ip_key, sessions_limit)

    if not await run_in_threadpool(check_rate):
        raise HTTPException(429, "rate_limited")
    if not await services.turnstile.verify(body.turnstile_token, ip):
        raise HTTPException(403, "verification_failed")
    token, session = services.signer.issue()
    return SessionResponse(session_token=token, expires_at=session.expires_at)


@router.post("/chat")
async def chat(
    body: ChatRequest, request: Request, settings: SettingsDep, services: ServicesDep
) -> StreamingResponse:
    database = _database(services)
    session = _session_from(request, services)
    if session is None:
        return _single_event(401, "invalid_session")
    history = body.history[-settings.max_history_turns :] if settings.max_history_turns else []
    if len(body.question) > settings.max_question_chars or any(
        len(t.question) + len(t.answer) > settings.max_history_chars for t in history
    ):
        return _single_event(422, "input_too_long")

    salt = settings.ip_hash_salt.get_secret_value()
    keys = [
        (
            hash_client(salt, "session", session.session_id),
            Limit("session-minute", 60, settings.rate_session_per_minute),
        ),
        (
            hash_client(salt, "session", session.session_id),
            Limit("session-day", 86400, settings.rate_session_per_day),
        ),
        (
            hash_client(salt, "ip", client_ip(request)),
            Limit("ip-hour", 3600, settings.rate_ip_per_hour),
        ),
    ]

    def admit() -> str | None:
        with database.connection() as conn:
            results = [limits.hit(conn, key, limit) for key, limit in keys]
            if not all(results):
                return "rate_limited"
            if limits.spent_today_usd(conn) >= settings.daily_spend_cap_usd:
                return "spend_cap"
        return None

    refusal = await run_in_threadpool(admit)
    if refusal == "rate_limited":
        return _single_event(429, "rate_limited")
    if refusal == "spend_cap":
        await run_in_threadpool(_log, database, session, body.question, "spend_cap", None, None)
        return _single_event(503, "spend_cap")

    turns = [Turn(t.question, t.answer) for t in history]
    return _stream(_answer(body, turns, session, settings, services, database))


def _session_from(request: Request, services: Services) -> Session | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if services.signer is None or scheme.lower() != "bearer" or not token:
        return None
    try:
        return services.signer.verify(token)
    except InvalidSessionError:
        return None


async def _answer(
    body: ChatRequest,
    history: list[Turn],
    session: Session,
    settings: Settings,
    services: Services,
    database: Database,
) -> AsyncIterator[bytes]:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    retrieved: RetrievalResult | None = None
    result: GenerationResult | None = None
    status = "error"
    citations_valid: bool | None = None
    try:
        query = retrieval_query(body.question, history)

        def retrieve() -> tuple[RetrievalResult, dict[str, list[str]], list[str]]:
            with database.connection() as conn:
                found = services.retriever.retrieve(
                    conn, query, top_n=settings.top_n, project=body.project
                )
                return found, _guardrails(conn, found), _topics(conn, found)

        found, guardrails, topics = await run_in_threadpool(retrieve)
        retrieved = found
        timings.update({f"retrieval_{k}": v for k, v in found.timings_ms.items()})
        evidence = Evidence.from_chunks(found.chunks)
        yield _sse("retrieval", _retrieval_event(found, evidence))

        if not has_enough_evidence(found.chunks, settings.evidence_min_similarity):
            status = "no_evidence"
            yield _sse("token", {"text": NO_EVIDENCE})
            yield _sse("citations", {"used": [], "removed": [], "unsupported": []})
            yield _sse("done", {"status": status, "suggestions": topics})
            return

        request = build_request(
            answer_system_prompt(),
            body.question,
            history,
            evidence,
            guardrails,
            settings.max_output_tokens,
        )

        def within_cap() -> bool:
            with database.connection() as conn:
                spent = limits.spent_today_usd(conn)
            estimate = services.provider.estimate_max_cost_usd(request)
            return spent + estimate <= settings.daily_spend_cap_usd

        if not await run_in_threadpool(within_cap):
            status = "spend_cap"
            yield _sse("error", {"code": "spend_cap", "message": MESSAGES["spend_cap"]})
            return

        citations = CitationFilter(frozenset(evidence.chunks))
        t = time.perf_counter()
        async for item in services.provider.stream(request):
            if isinstance(item, GenerationResult):
                result = item
                continue
            text = citations.feed(item)
            if text:
                yield _sse("token", {"text": text})
        tail = citations.flush()
        if tail:
            yield _sse("token", {"text": tail})
        timings["generate"] = round((time.perf_counter() - t) * 1000, 2)

        unsupported = unsupported_sentences(citations.text)
        citations_valid = not citations.removed and not unsupported
        yield _sse(
            "citations",
            {
                "used": [_citation(cid, evidence) for cid in citations.used],
                "removed": citations.removed,
                "unsupported": unsupported,
            },
        )
        status = "refused" if result and result.stop_reason == "refusal" else "answered"
        yield _sse("done", {"status": status})
    except (RetrievalError, ProviderError, psycopg.Error) as exc:
        logger.warning("chat failed: %s", exc)
        yield _sse("error", {"code": "unavailable", "message": MESSAGES["unavailable"]})
    except Exception:
        logger.exception("unexpected chat failure")
        yield _sse("error", {"code": "unavailable", "message": MESSAGES["unavailable"]})
    finally:
        timings["total"] = round((time.perf_counter() - started) * 1000, 2)
        try:
            await run_in_threadpool(
                _log,
                database,
                session,
                body.question,
                status,
                retrieved,
                result,
                timings,
                citations_valid,
            )
        except psycopg.Error:
            logger.exception("could not write query log")


def _retrieval_event(found: RetrievalResult, evidence: Evidence) -> dict[str, Any]:
    return {
        "method": found.method,
        "index_version": found.index_version,
        "timings_ms": found.timings_ms,
        "chunks": [
            {
                "id": cid,
                "chunk_id": c.chunk_id,
                "title": c.document_title,
                "section": c.section,
                "url": c.citation_url,
                "project": c.project_slug,
                "vector_score": c.vector_score,
                "keyword_score": c.keyword_score,
                "fused_score": c.fused_score,
            }
            for cid, c in evidence.chunks.items()
        ],
    }


def _citation(cid: str, evidence: Evidence) -> dict[str, Any]:
    chunk = evidence.chunks[cid]
    return {
        "id": cid,
        "chunk_id": chunk.chunk_id,
        "title": chunk.document_title,
        "section": chunk.section,
        "url": chunk.citation_url,
    }


def _guardrails(conn: psycopg.Connection, found: RetrievalResult) -> dict[str, list[str]]:
    slugs = sorted({c.project_slug for c in found.chunks if c.project_slug})
    if not slugs:
        return {}
    rows = conn.execute(
        "SELECT slug, guardrails FROM projects WHERE index_version = %s AND slug = ANY(%s)",
        (found.index_version, slugs),
    ).fetchall()
    return {str(slug): [str(rule) for rule in rules] for slug, rules in rows}


def _topics(conn: psycopg.Connection, found: RetrievalResult) -> list[str]:
    rows = conn.execute(
        "SELECT title FROM projects WHERE index_version = %s ORDER BY title LIMIT 5",
        (found.index_version,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _log(
    database: Database,
    session: Session,
    question: str,
    status: str,
    retrieved: RetrievalResult | None,
    result: GenerationResult | None,
    timings: dict[str, float] | None = None,
    citations_valid: bool | None = None,
) -> None:
    chunks = retrieved.chunks if retrieved else []
    with database.connection() as conn:
        conn.execute(
            "INSERT INTO query_logs (session_id, question, retrieved, answer_status, model,"
            " tokens_in, tokens_out, cost_usd, stage_timings_ms, citations_valid)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session.session_id,
                question,
                json.dumps(
                    [
                        {"chunk_id": c.chunk_id, "fused": c.fused_score, "vector": c.vector_score}
                        for c in chunks
                    ]
                ),
                status,
                result.model if result else None,
                result.tokens_in if result else 0,
                result.tokens_out if result else 0,
                result.cost_usd if result else 0,
                json.dumps(timings or {}),
                citations_valid,
            ),
        )


@router.get("/sources/{chunk_id}")
async def get_source(chunk_id: int, services: ServicesDep) -> dict[str, Any]:
    database = _database(services)

    def fetch() -> tuple[Any, ...] | None:
        with database.connection() as conn:
            version, _ = active_index(conn)
            return conn.execute(
                "SELECT c.id, c.section, c.anchor, c.text, d.title, d.url, d.project_slug"
                " FROM chunks c JOIN documents d ON d.id = c.document_id"
                " WHERE c.id = %s AND c.index_version = %s",
                (chunk_id, version),
            ).fetchone()

    try:
        row = await run_in_threadpool(fetch)
    except RetrievalError as exc:
        raise HTTPException(503, "unavailable") from exc
    if row is None:
        raise HTTPException(404, "not_found")
    cid, section, anchor, text, title, url, project = row
    return {
        "chunk_id": cid,
        "title": title,
        "section": section,
        "url": f"{url}#{anchor}",
        "project": project,
        "text": text,
    }


@router.get("/projects")
async def list_projects(services: ServicesDep) -> dict[str, Any]:
    database = _database(services)

    def fetch() -> list[tuple[Any, ...]]:
        with database.connection() as conn:
            version, _ = active_index(conn)
            return conn.execute(
                "SELECT slug, title, summary, type, period, repo_url, tags FROM projects"
                " WHERE index_version = %s ORDER BY title",
                (version,),
            ).fetchall()

    try:
        rows = await run_in_threadpool(fetch)
    except RetrievalError as exc:
        raise HTTPException(503, "unavailable") from exc
    keys = ("slug", "title", "summary", "type", "period", "repo_url", "tags")
    return {"projects": [dict(zip(keys, row, strict=True)) for row in rows]}
