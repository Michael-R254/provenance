# 0001: Stack and repository layout

- Status: accepted
- Date: 2026-11-25

## Context

Provenance is a public portfolio site with a RAG-powered guide. It must be cheap to run (free tiers
where possible), reliable for recruiters, and a credible example of production AI engineering that
Michael can explain in interviews. Full reasoning is in `docs/architecture.md`.

## Decision

- One monorepo: `apps/web` (Next.js, TypeScript, Tailwind), `apps/api` (FastAPI, Python 3.12, uv),
  `ingest/`, `evals/`, `content/`, `db/`.
- Postgres with pgvector for vectors, full-text search, graph and logs in one database (Neon in
  production, `docker compose` locally).
- Hosting: Vercel (web), Google Cloud Run (api). Homelab for development only.
- LLM behind an `LLMProvider` interface: Claude Haiku 5.5 in production, Ollama locally, a mock in
  tests. Local embeddings with `bge-small-en-v1.5`.
- No RAG framework (LangChain, LlamaIndex) and no separate vector database.
- Tooling: pnpm, ESLint, Prettier, Vitest, Playwright with axe; uv, ruff, mypy (strict), pytest;
  GitHub Actions.

## Consequences

- Retrieval and generation logic is plain code that we own, test and can explain line by line.
- One database keeps operations simple, at the cost of tuning pgvector ourselves.
- Two languages in one repo means two toolchains in CI; jobs run in parallel to keep it fast.
