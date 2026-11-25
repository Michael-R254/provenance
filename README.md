# Provenance

An AI guide to Michael Rollinson's engineering work. Hybrid RAG over approved project docs, with
cited answers, evaluation in CI and a transparency view.

## Repository

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js site |
| `apps/api` | FastAPI service |
| `content/` | Approved project write-ups (the RAG corpus) |
| `db/` | Local init scripts and SQL migrations |
| `docs/` | Architecture, milestones and decision records |

Plan and design: [`docs/architecture.md`](docs/architecture.md),
[`docs/milestones.md`](docs/milestones.md). Agent rules: [`AGENTS.md`](AGENTS.md).

## Local setup

Requirements: Node 22 with pnpm 10, Python 3.12 with uv, Docker.

```bash
cp .env.example .env
docker compose up -d db

pnpm --dir apps/web install
pnpm --dir apps/web exec playwright install chromium
pnpm --dir apps/web dev            # http://localhost:3000

cd apps/api && uv sync
uv run uvicorn provenance.main:app --reload   # http://localhost:8000/health
```

All checks are listed in [`AGENTS.md`](AGENTS.md#commands) and run in CI on every pull request.
