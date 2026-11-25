# Provenance architecture

Source of truth for how the system is built. Agreed with Michael on 25 Nov 2026. Change it only
through a pull request, with an ADR in `docs/decisions/` for significant changes.

## 1. Product summary

- A portfolio site for Michael Rollinson with an AI guide, **Provenance**, that answers questions
  about his work in the third person ("Mike built...") and cites the evidence.
- Visual direction: "Field Console". Evidence Console layout (answer left, evidence rail right,
  ⌘K command palette) with editorial typography (Newsreader headings, IBM Plex Sans body, IBM Plex
  Mono metadata), paper-toned light theme, deep-moss dark theme, one moss-green accent, amber for
  warnings only. No particles, glows or gradient blobs. Respect `prefers-reduced-motion`.
- Release plan:
  - **Wave 1 (launch):** chat with streaming and citations, generated project pages, recruiter
    mode (starter questions and ordering only), transparency drawer, evaluation in CI, safety
    controls, deployment.
  - **Wave 2:** knowledge graph (`/explore`), How it works page with pipeline and evaluation
    results, semantic citation checks, reranker experiment.

## 2. Pages

| Route | Wave | Purpose |
| --- | --- | --- |
| `/` | 1 | Intro, recruiter mode picker, starter questions, chat |
| `/projects` | 1 | Filterable index (a list or table, not a card grid) |
| `/projects/[slug]` | 1 | Generated from `content/projects/<slug>.md`; section anchors; "Ask about this project" |
| `/ask` | 1 | Full-screen chat (mobile) |
| `/about` | 1 | Profile, CV download, contact links |
| `/explore` | 2 | Knowledge graph with an accessible list view |
| `/how-it-works` | 2 | Pipeline stages and latest evaluation results |

On every page: command palette, chat panel, recruiter mode, theme toggle.

The chat panel lives on `/` and `/ask` and talks to the API directly from the browser
(`NEXT_PUBLIC_API_URL`). Recruiter mode stays in the browser. Reviewed starter answers come from
`content/starters.yaml` (approved entries only). See ADR 0006.

Pages are built from approved files in `content/` only, with a post-build check that no draft
id or title appears in the output. Section ids match ingestion anchors. See ADR 0005.

## 3. Components and hosting

```text
Browser ──pages──> Vercel (Next.js, static project pages)
Browser ──chat (SSE)──> Cloud Run (FastAPI) ──> Claude API (Haiku 5.5)
                             │ read only
                             v
                        Neon Postgres + pgvector
GitHub Actions ──ingest (only writer)──> Neon
GitHub Actions ──deploy──> Vercel, Cloud Run
Homelab: development only (Ollama + Gemma), never serves public traffic
```

- Cold starts: the frontend calls `GET /health` on page load to wake the API and database. The chat
  shows "Waking up the guide…" if the first answer is slow.
- Cloud Run: scale to zero, `max-instances` capped (start at 2).

## 4. RAG pipeline

### Ingestion (CI, on merge to `main` touching `content/` or `ingest/`)

1. Read `content/**/*.md`.
2. Validate frontmatter against the schema; **reject anything not `status: approved`**.
3. Chunk by `##` section; split long sections on paragraph boundaries with a small overlap. Each
   chunk keeps `project_slug`, `section`, `anchor` (matches the page's heading id), `ordinal`.
   Exact rules: `docs/decisions/0002-chunking-and-anchors.md`.
4. Embed with `BAAI/bge-small-en-v1.5` via `fastembed` (384 dims). Normalise vectors.
5. Write a new `index_versions` row (`status = building`) and its documents, chunks and graph rows.
6. Run the retrieval evaluation against the new version. If it passes the gate, set it `active`
   and the previous one `retired`. Otherwise leave the old version active and fail the job.

### Query (live, per question)

1. **Input:** question, `session_id`, last few turns, optional `project` scope. Role is NOT sent.
2. **Guard:** Turnstile-verified session token, rate limits, max question length, daily spend cap.
3. **Rewrite follow-ups** into a standalone query when history is present (rule-based: short or
   pronoun-led questions are joined to the previous question; no model call. See ADR 0004).
4. **Hybrid retrieve** from the active index: pgvector cosine top-k and full-text top-k (any
   query term may match; `ts_rank_cd` orders), optional project filter. See ADR 0003.
5. **Fuse** with reciprocal rank fusion (k = 60 as a starting point; tune from evaluation).
6. **Evidence threshold:** if the best vector similarity is below `evidence_min_similarity`
   (placeholder 0.35, to be set from evaluation data with the real embedder), return a
   "no evidence" answer that suggests supported related topics. No generation call.
7. **Assemble context:** top chunks with stable IDs like `[c3]`, plus `guardrails` for each project
   represented.
8. **Generate** with streaming. The system prompt requires a citation ID on every factual claim and
   says retrieved text and user text are data, not instructions.
9. **Validate citations:** remove citation IDs that were not supplied; mark sentences without valid
   support. (Wave 2: lightweight semantic support check.)
10. **Stream and log** to `query_logs`.

## 5. Database schema (Postgres)

| Table | Key columns |
| --- | --- |
| `index_versions` | `id`, `git_sha`, `embedding_model`, `chunker_version`, `status` (building, active, retired, failed), `created_at`, `activated_at` |
| `projects` | `slug`, `title`, `summary`, `type`, `period`, `repo_url`, `tags jsonb`, `guardrails jsonb`, `index_version` |
| `documents` | `id`, `project_slug`, `title`, `doc_type` (project, profile), `source_path`, `url`, `version`, `content_hash`, `index_version` |
| `chunks` | `id`, `document_id`, `section`, `anchor`, `ordinal`, `text`, `token_count`, `embedding vector(384)`, `tsv tsvector` (generated), `index_version` |
| `entities` | `id`, `kind` (project, skill, language, framework, model, research_area), `label`, `index_version` |
| `entity_links` | `source_id`, `target_id`, `relation`, `evidence_chunk_id` |
| `query_logs` | `id`, `session_id`, `created_at`, `question`, `retrieved jsonb`, `answer_status`, `model`, `tokens_in`, `tokens_out`, `cost_usd`, `stage_timings_ms jsonb`, `citations_valid` |
| `rate_limits` | `key` (salted hash of IP or session), `window_start`, `count` |
| `eval_runs` | `id`, `git_sha`, `model`, `dataset_version`, `metrics jsonb`, `created_at` |

Indexes: HNSW on `chunks.embedding`, GIN on `chunks.tsv`, btree on `index_version` columns.
Privacy: visitor questions are stored; IP addresses are never stored, only salted hashes in
`rate_limits`, deleted after 24 hours.

## 6. API (FastAPI)

| Endpoint | Wave | Notes |
| --- | --- | --- |
| `POST /v1/chat` | 1 | SSE stream of events: `retrieval`, `token`, `citations`, `done`, `error` |
| `POST /v1/session` | 1 | Verifies a Cloudflare Turnstile token, returns a short-lived signed session token |
| `GET /v1/projects` | 1 | Project list for palette and index |
| `GET /v1/sources/{chunk_id}` | 1 | Chunk text and metadata for evidence cards |
| `GET /v1/graph` | 2 | Nodes and edges for the active index |
| `GET /v1/eval/latest` | 2 | Latest evaluation metrics |
| `GET /health` | 1 | Readiness; wakes API and database |

CORS allows only the site's own origins. Errors to visitors are generic; details go to logs.

**`POST /v1/session`** takes `{"turnstile_token"}` and returns `{"session_token", "expires_at"}`
(HMAC-signed, one hour). Errors: 403 `verification_failed`, 429 `rate_limited` (per IP hash).

**`POST /v1/chat`** takes `{"question", "history": [{"question", "answer"}], "project"}` with a
`Authorization: Bearer <session_token>` header. Unknown fields (including `role`) are rejected
with 422. The response is always `text/event-stream`:

| Event | Data |
| --- | --- |
| `retrieval` | `method`, `index_version`, `timings_ms`, `chunks` (`id` like `c1`, `chunk_id`, title, section, url, scores) |
| `token` | `text` (citation markers like `[c1]` inline; unknown IDs already removed) |
| `citations` | `used` (id, chunk_id, title, section, url), `removed` (unknown IDs), `unsupported` (sentences without a citation) |
| `done` | `status`: `answered`, `no_evidence` (with `suggestions`) or `refused` |
| `error` | `code` and a visitor-safe `message`. Codes: `invalid_session` (401), `input_too_long` (422), `rate_limited` (429), `spend_cap` (503, or mid-stream before generation), `unavailable` |

Prompt text lives in `apps/api/src/provenance/prompts/answer-v1.md` and is never returned. The
OpenAPI schema is disabled in production. See ADR 0004.

## 7. Cost and abuse controls

Layered, in order of what stops spend:

1. Anthropic prepaid credit with auto-reload off (hard ceiling, configured by Michael).
2. Daily global spend cap in the API (from `query_logs.cost_usd`); when reached, chat returns a
   "the guide is resting, come back tomorrow" message.
3. Cloudflare Turnstile before a session token is issued; signed, short-lived session tokens.
4. Per-IP-hash and per-session fixed-window rate limits.
5. Max question length, history turns and `max_tokens` on generation.
6. Starter questions served from pre-generated, reviewed answers (no model call).
7. Cloud Run `max-instances` cap; Google Cloud budget alert.

## 8. Evaluation

- `evals/datasets/questions.yaml`: categories single-project factual (15), multi-project (8), recruiter
  open-ended (8), distinction checks (4), unanswerable (8), adversarial and injection (7). Each
  question lists expected chunk anchors and must-contain / must-not-contain facts. Questions are
  written with Michael; never generated from the system's own answers.
- Retrieval metrics on every pull request: recall@k, hit@k, MRR, per method (hybrid, vector,
  keyword), over the fictional fixture corpus in `evals/fixtures/` (`evals/datasets/fixture.yaml`).
  CI fails if hybrid recall@k or MRR drops below `evals/baselines/fixture-retrieval.json`.
- Generation metrics on demand and before release: citation validity, groundedness and required
  facts (Claude Opus 5.5 as judge with a fixed rubric; Claude Haiku 5.5 optional for cheap runs;
  ADR 0008), correct refusal rate, latency, cost.
- Release gate: retrieval recall must not drop; every distinction check passes; no adversarial
  question produces a fabricated claim. Numeric thresholds are set after the first baseline.
- Recruiter mode check: the same question under every role yields the same facts. Checked
  structurally: the API rejects a role field, and each role's session produces a byte-identical
  generation request (ADR 0008).
- Runner: `python -m evals.generation` drives the real API in process, prints an expected and
  worst-case cost from a free dry run, and spends nothing without `--yes`; `--max-cost` is a hard
  limit. Fictional generation questions: `evals/datasets/fixture-generation.yaml`; rubric:
  `evals/rubrics/judge-v1.md`; proposed thresholds: `evals/thresholds.yaml`. Launch steps:
  `docs/launch-checklist.md`.

## 9. CI/CD

| Workflow | Trigger | Does |
| --- | --- | --- |
| `ci` | pull request | lint, types, unit and integration tests, Playwright + axe, Lighthouse CI, content validation, retrieval evaluation on a throwaway index, API image build |
| `eval-generation` | manual or `run-evals` label | full generation evaluation; comments a summary on the pull request |
| `deploy` | merge to `main` | migrations, then Cloud Run deploy with a `/health` smoke test, then Vercel deploy |
| `ingest` | merge to `main` touching `content/` or `ingest/` | new index version, structural check and retrieval gate on that version, activate or mark failed and keep previous |
| `rollback-index` | manual | list versions, or activate an earlier one |

Production jobs run only when the repository variable `DEPLOY_ENABLED` is `true`. Migrations,
ingest and rollback share one concurrency group. Secrets, roles and budget alerts: README
"Deployment". Operations: [`docs/runbook.md`](runbook.md). Rationale: ADR 0007.
