# 0007: Deployment, gated ingest and operations

- Status: accepted
- Date: 2026-11-25

## Context

M6 puts the site live on Vercel, Cloud Run and Neon (architecture section 3) with GitHub Actions
as the only deployer and the only writer of the corpus. It has to stay within about £10 a month,
keep every secret in a platform store, and let Michael undo a bad content change quickly. The
retrieval evaluation built in M2 only worked by wiping a throwaway database, which cannot be
pointed at production.

## Decision

- **Deploy order: migrate, API, site.** One `deploy` workflow on every merge to `main`.
  Migrations are additive only and run first; the API ships next and is smoke-tested on
  `/health`; the site ships last, so it never points at an API that is not live yet.
- **Site built in Actions, not by Vercel's Git integration.** `vercel build` runs in the checked
  out repository, so the build sees `content/` at the root, and `vercel.json` turns Git
  deployments off so there is exactly one deployer. Public values (`NEXT_PUBLIC_*`) stay in the
  Vercel project and are pulled at build time.
- **Container.** `apps/api/Dockerfile` installs from `uv.lock`, bakes the embedding model into the
  image (no download on a cold start, `HF_HUB_OFFLINE=1`), runs as a non-root user, and defaults
  to `PROVENANCE_ENVIRONMENT=production`, so the settings validator refuses to start without real
  secrets. CI builds the image on every pull request.
- **Cloud Run settings.** Scale to zero, `max-instances 2`, concurrency 20, 1 CPU, 1 GiB,
  60 second timeout. Plain settings come from a generated env file on each deploy, and secrets
  from Secret Manager. GitHub signs in with Workload Identity Federation, so there is no Google
  key file.
- **Production CORS.** The validator now requires exact `https` origins with no wildcard or
  localhost. Origins come from the `PRODUCTION_ORIGINS` repository variable.
- **Least-privilege database roles.** The API connects as `provenance_api`
  (`db/roles/api-role.sql`): read the corpus, insert logs, maintain rate limits, nothing else.
  Migrations and ingest use the owner role from GitHub secrets.
- **Gated ingest without touching the live index.** `ingest run` (without `--activate`) builds a
  `building` version beside the active one. Two gates then run against that version:
  1. `ingest check`: the version holds exactly the approved files, each with all of its chunks,
     the project rows match, and it was embedded with the model the API queries with.
  2. Retrieval quality: `evals.retrieval --index-version N` scores the candidate in place, read
     only, against `evals/datasets/questions.yaml` and `evals/baselines/content-retrieval.json`.
     Until Michael and I write that question set, this gate is skipped with a warning and only
     the structural gate applies.

  Pass: `ingest activate`. Fail: `ingest mark-failed`, and the previous version stays live. The
  retriever gained an `index_version` argument for this; the public API never passes it.
- **Shared database lock.** Migrations, ingest and index rollback share one concurrency group,
  so they never run at the same time.
- **Switched off until ready.** Every production job requires the variable `DEPLOY_ENABLED` to
  be `true`, so merging this milestone does nothing until the accounts exist.
- **Spend cap as configuration.** `DAILY_SPEND_CAP_USD` is a repository variable written on every
  deploy, so pausing chat with a cap of 0 survives redeploys.
- **Monitoring stays small.** `python -m provenance.report` summarises `query_logs` per day (cost,
  tokens, p50/p95 latency, citation problems) without printing questions. Cloud Run logs and the
  Google Cloud budget alert cover the rest. No paid monitoring service.

## Consequences

- Rolling back content is a single `activate` of a retired version, in one transaction, via the
  `rollback-index` workflow. No rebuild and no laptop holding the owner password.
- A content merge before the real question set exists is only checked structurally. That is
  acceptable for the first content but should not last: writing `questions.yaml` is part of M7.
- Vercel preview deployments for pull requests are off, because Git deployments are off. The
  CI build and Playwright run cover pull requests instead.
- No Content-Security-Policy yet. The site sets `nosniff`, `X-Frame-Options`, `Referrer-Policy`
  and `Permissions-Policy`. A CSP with Turnstile and the API origin is a follow-up once the
  production domains are known.
