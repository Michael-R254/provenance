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

## Deployment

A merge to `main` runs [`deploy`](.github/workflows/deploy.yml): database migrations, then the API
on Google Cloud Run, then the site on Vercel. A merge that changes `content/` or `ingest/` also
runs [`ingest`](.github/workflows/ingest.yml), which builds a new index beside the live one and
activates it only if it passes its gates. Both stay switched off until the repository variable
`DEPLOY_ENABLED` is `true`. Day-to-day operations (rollback, key rotation, pausing chat) are in
[`docs/runbook.md`](docs/runbook.md).

| Service | Plan | Used for |
| --- | --- | --- |
| Vercel | Hobby (free) | the site |
| Google Cloud Run | pay per use, scales to zero, at most 2 instances | the API |
| Neon | free tier | Postgres with pgvector |
| Anthropic | prepaid credit, auto-reload off | answers (Claude Haiku 5.5) |
| Cloudflare Turnstile | free | bot check before a chat session |

### Which secret goes where

Nothing secret is ever committed. Each value lives in exactly one store.

| Value | Store | Name |
| --- | --- | --- |
| Anthropic API key | Google Secret Manager | `provenance-anthropic-api-key` |
| Session signing secret (64 random characters) | Google Secret Manager | `provenance-session-secret` |
| Turnstile secret key | Google Secret Manager | `provenance-turnstile-secret` |
| IP hash salt (32 random characters) | Google Secret Manager | `provenance-ip-hash-salt` |
| Neon URL for the `provenance_api` role ([grants](db/roles/api-role.sql)) | Google Secret Manager | `provenance-api-database-url` |
| Neon URL for the owner role (migrations) | GitHub Actions secret | `NEON_MIGRATE_DATABASE_URL` |
| Neon URL for the owner role (ingest, rollback) | GitHub Actions secret | `NEON_INGEST_DATABASE_URL` |
| Vercel access token | GitHub Actions secret | `VERCEL_TOKEN` |
| API address, e.g. `https://api.example.org` | Vercel environment variable (Production) | `NEXT_PUBLIC_API_URL` |
| Turnstile site key (public) | Vercel environment variable (Production) | `NEXT_PUBLIC_TURNSTILE_SITE_KEY` |

These are configuration, not secrets, and live in GitHub Actions **variables**:
`DEPLOY_ENABLED`, `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`,
`GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_RUNTIME_SERVICE_ACCOUNT`, `PRODUCTION_ORIGINS` (comma
separated, e.g. `https://example.org,https://www.example.org`), `DAILY_SPEND_CAP_USD` (optional,
default 1.0), `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

GitHub reaches Google Cloud through Workload Identity Federation, so no Google key file exists
anywhere. The runtime service account needs only `roles/secretmanager.secretAccessor` on the five
secrets above.

### Budget alerts

Spending is capped in layers (see [architecture section 7](docs/architecture.md#7-cost-and-abuse-controls)).
The two you set up by hand:

1. **Anthropic:** buy a small prepaid credit (for example $5) and leave auto-reload **off**. When
   the credit runs out, answers stop; nothing is billed beyond it. The API's own daily cap
   (`DAILY_SPEND_CAP_USD`, default $1) normally stops it well before that.
2. **Google Cloud:** Billing > Budgets & alerts > Create budget. Scope it to this project, set a
   monthly amount (for example £5), and keep the default email alerts at 50%, 90% and 100%. A
   budget alert only emails you; it does not stop spending. If it fires, pause chat as described
   in the runbook.

Vercel Hobby, the Neon free tier and Turnstile need no payment card, so they cannot bill.

### Usage report

```bash
PROVENANCE_DATABASE_URL='<provenance_api role URL>' \
  uv run --project apps/api python -m provenance.report --days 7
```

Prints questions, answers, tokens, cost and p50/p95 latency per day, and never prints visitors'
questions.
