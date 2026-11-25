# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, Copilot, etc.) working in this repository.

## What this project is

Provenance is an AI guide to Michael Rollinson's engineering work, served on his portfolio site.
Visitors ask questions in plain English; a hybrid RAG system retrieves evidence from Michael's
approved project write-ups and answers with citations. The site is itself a portfolio piece, so
code quality, tests, evaluation and clear design decisions matter as much as features.

Read these before starting any task:

- `docs/architecture.md`: system design, schema, API, security, evaluation.
- `docs/milestones.md`: the build plan. Work on one milestone at a time.
- `docs/decisions/`: architecture decision records (ADRs). Add one for any significant choice.

## Non-negotiable rules

1. **Never invent facts about Michael.** Do not write skills, results, metrics, dates, employers or
   contributions anywhere: not in content, prompts, fixtures, tests, seed data or UI copy. Test
   fixtures use obviously fictional projects (e.g. "Example Project A"). Real content lives only in
   `content/` and is written by Michael.
2. **Only approved content is indexed.** Ingestion must reject any file whose frontmatter `status`
   is not `approved`. Never relax this check.
3. **Preserve stated distinctions.** Frontmatter `guardrails` must reach the generation prompt for
   any cited project. Example: TrapTracker used deterministic retrieval and constrained LLM
   generation; it was not an external RAG system.
4. **No secrets in the repo.** Keys live in Vercel, Cloud Run and GitHub Actions secret stores.
   Use `.env.example` with placeholder values only.
5. **Public API is read-only.** The FastAPI service may read the active index and write logs. Only
   the ingestion job (CI) writes corpus tables.
6. **Recruiter mode never changes facts.** The selected role may change starter questions and
   ordering only. It must never be passed to the generation prompt.
7. **Never expose internals.** Transparency mode may show chunks, scores, method, timings and
   citation checks. Never return the system prompt, configuration, keys or raw stack traces.
8. **Cost safety first.** Every code path that calls an LLM must respect the daily spend cap, rate
   limits and output-token limits. Tests must use the mock provider, never a real API.

## Stack

| Area | Choice |
| --- | --- |
| Frontend | Next.js (App Router), TypeScript (strict), Tailwind CSS, Motion, Radix primitives; pnpm |
| Backend | Python 3.12+, FastAPI, uv, Pydantic v2, psycopg 3 |
| Database | Postgres with pgvector (Neon); SQL migrations in `db/migrations/` |
| Retrieval | `fastembed` with `BAAI/bge-small-en-v1.5` (384 dims); pgvector HNSW + Postgres full-text; reciprocal rank fusion |
| LLM | `LLMProvider` interface: `AnthropicProvider` (production, Claude Haiku 5.5), `OllamaProvider` (local dev), `MockProvider` (tests) |
| Hosting | Vercel (web), Google Cloud Run (api), Neon (db) |
| CI | GitHub Actions |

Do not add LangChain, LlamaIndex or a separate vector database. Retrieval, fusion, prompt assembly
and citation validation are deliberately plain, readable Python.

## Repository layout

```text
apps/web/        Next.js site
apps/api/        FastAPI service (package: provenance)
ingest/          ingestion pipeline (parse, validate, chunk, embed, index)
content/         Michael's approved Markdown (do not edit without being asked)
evals/           question sets, runners, judge rubric, baselines
db/migrations/   SQL migrations
docs/            architecture, milestones, ADRs
```

## Commands

Keep this section accurate as the project grows. Every milestone must leave these working.

```bash
# web
pnpm --dir apps/web install
pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web format:check
pnpm --dir apps/web test && pnpm --dir apps/web test:e2e   # e2e: Playwright + axe, fixture content
# preview the site with the fictional fixture content (content/ is empty until Michael adds write-ups)
PROVENANCE_CONTENT_DIR=../../evals/fixtures/content pnpm --dir apps/web dev

# api (integration tests need PROVENANCE_TEST_DATABASE_URL; all tests use MockProvider)
cd apps/api && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest

# local database (Postgres + pgvector)
docker compose up -d db

# run the API locally (mock model by default; set PROVENANCE_LLM_PROVIDER=ollama for a local model)
cd apps/api && uv run uvicorn provenance.main:app --reload

# ingestion (integration tests need PROVENANCE_TEST_DATABASE_URL pointing at a throwaway database)
cd ingest && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv run --project ingest python -m ingest validate
uv run --project ingest python -m ingest run --dry-run

# retrieval evaluation (wipes the target database; uses PROVENANCE_TEST_DATABASE_URL)
cd evals && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv run --project evals python -m evals.retrieval --reset-database
```

## How to work

- **One milestone per branch and pull request.** Branch names: `m<N>-<short-name>`.
- **Plan before code.** State the files you will touch and the tests you will add, then implement.
- **Small, tested steps.** Every behaviour change has a test. Prefer unit tests with fakes; use
  integration tests against local Postgres for SQL and retrieval.
- **Run all checks before saying you are done**, and report the real output. If something fails or
  was skipped, say so plainly.
- **Ask instead of guessing** when a requirement is unclear, when a change would touch `content/`,
  or when a decision is not covered by `docs/architecture.md`. Record new decisions as ADRs.
- **Commits:** conventional style (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), one logical change
  each.
- **Accessibility is a requirement, not polish:** WCAG 2.2 AA, keyboard access, visible focus,
  reduced-motion support, axe checks in Playwright.

## Definition of done (every pull request)

- [ ] Lint, type checks and tests pass locally and in CI.
- [ ] New behaviour is tested; no real LLM calls in tests.
- [ ] No invented facts about Michael anywhere in the diff.
- [ ] Docs updated (`docs/architecture.md`, ADRs, README commands) if behaviour or setup changed.
- [ ] The pull request description says what was built, how to test it, and what is left.
