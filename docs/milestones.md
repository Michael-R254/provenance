# Milestones

Each milestone is one branch and one pull request. Do them in order. Each has a goal, scope,
acceptance criteria, and a prompt Michael can paste into Claude Code to start it.

Every prompt assumes the agent has read `AGENTS.md` and `docs/architecture.md`.

---

## M0: Scaffold, tooling and CI

**Goal:** an empty but fully wired monorepo where every check runs green.

**Scope:** directory layout from AGENTS.md; Next.js app with TypeScript strict, Tailwind, ESLint,
Prettier, Vitest, Playwright with axe; FastAPI app with uv, ruff, mypy, pytest and a `/health`
endpoint; `docker-compose.yml` with Postgres + pgvector for local dev; `.env.example` files; GitHub
Actions `ci` workflow running all checks; README with setup commands; `docs/decisions/0001-stack.md`.

**Acceptance criteria**
- [ ] `pnpm` lint, typecheck, unit test and Playwright (one smoke test with axe) pass.
- [ ] `uv run` ruff, mypy and pytest pass; `/health` returns 200 in a test.
- [ ] `docker compose up -d db` starts Postgres with the `vector` extension available.
- [ ] CI runs all of the above on pull requests.
- [ ] No secrets committed; `.env.example` holds placeholders only.

**Prompt**
> Read AGENTS.md and docs/architecture.md. We are on milestone M0 in docs/milestones.md. Create
> branch `m0-scaffold`. Propose the file tree and tool versions (latest stable) first, then build
> the scaffold so every acceptance criterion passes. Run all checks, report the real results, and
> open a pull request. Do not build any product features yet.

---

## M1: Content schema, validator and ingestion

**Goal:** approved Markdown becomes a versioned, searchable index.

**Scope:** SQL migrations for every table in architecture section 5; Pydantic frontmatter schema
matching `content/_template.md`; validator CLI that rejects non-approved files and reports errors
clearly; heading-aware chunker; `fastembed` embedder behind an `Embedder` interface (with a fake for
tests); index writer that creates a new `index_versions` row; activation step. Fixtures use
fictional projects only.

**Acceptance criteria**
- [ ] A `status: draft` file is never indexed (tested).
- [ ] Chunks keep `project_slug`, `section`, `anchor`, `ordinal`; anchors match the slug rules the
      web app will use (documented in an ADR).
- [ ] Re-running ingestion creates a new index version; activation retires the previous one.
- [ ] `python -m ingest --dry-run` prints a per-file summary without writing.
- [ ] Integration tests run against docker Postgres in CI.

**Prompt**
> Milestone M1. Branch `m1-ingestion`. Read docs/architecture.md sections 4 and 5 and
> content/_template.md. Plan the modules and tests first. Implement migrations, frontmatter schema,
> validator, chunker, embedder interface, index writer and activation. Use only fictional fixture
> content. Run all checks and open a pull request.

---

## M2: Hybrid retrieval and retrieval evaluation

**Goal:** given a query, return well-ranked chunks, with measured quality.

**Scope:** `retrieval` module with vector search, full-text search and reciprocal rank fusion;
optional project filter; reads only the active index; `evals/questions.yaml` format and a retrieval
evaluation runner (recall@k, MRR, per method) with a fixture question set; CI job that runs it.

**Acceptance criteria**
- [ ] Each method and the fusion are unit tested with known rankings.
- [ ] Evaluation runner outputs a table and JSON; CI fails if recall drops below the stored baseline.
- [ ] Query latency for retrieval is logged per stage.

**Prompt**
> Milestone M2. Branch `m2-retrieval`. Implement hybrid retrieval and the retrieval evaluation
> runner per docs/architecture.md sections 4 and 8. Keep it plain Python, no RAG frameworks. Show
> me the evaluation output on the fixture set in the pull request description.

---

## M3: Generation, citations and the chat endpoint

**Goal:** a safe, streaming, cited answer from the API.

**Scope:** `LLMProvider` interface with `AnthropicProvider` (Claude Haiku 5.5, streaming, prompt
caching for the fixed system prompt), `OllamaProvider` and `MockProvider`; prompt assembly with
chunk IDs and guardrails; evidence threshold and "no evidence" path; citation validator; follow-up
rewrite; `POST /v1/session` with Turnstile verification; `POST /v1/chat` SSE events; rate limits,
daily spend cap, input and output limits; `query_logs` writes; `/v1/sources/{id}`, `/v1/projects`.

**Acceptance criteria**
- [ ] All tests use `MockProvider`; no network calls in CI.
- [ ] Unknown citation IDs are removed and reported in the `citations` event (tested).
- [ ] Weak evidence returns "no evidence" without calling the provider (tested).
- [ ] Spend cap and rate limits return the documented `error` event (tested).
- [ ] The role from recruiter mode is not accepted by `/v1/chat` (tested).
- [ ] Prompt text lives in one versioned file and is never returned by any endpoint.

**Prompt**
> Milestone M3. Branch `m3-chat-api`. Implement generation, citation validation, the session and
> chat endpoints, and all cost controls from docs/architecture.md sections 4, 6 and 7. Use the
> official Anthropic Python SDK for AnthropicProvider, but test only with MockProvider. Do not call
> any paid API. List every safety control and its test in the pull request description.

---

## M4: Site shell, design system and project pages

**Goal:** the static site looks and feels like Field Console, with real project pages.

**Scope:** design tokens (colour, type, spacing, motion) for light and dark themes; fonts
self-hosted and subset; app shell, nav, theme toggle, skip link; command palette (search only for
now); `/projects` index and `/projects/[slug]` generated at build time from `content/`; `/about`;
section anchors matching M1's anchor rules; reduced-motion handling.

**Acceptance criteria**
- [ ] Pages render without JavaScript; Lighthouse mobile performance 90 or more on a project page.
- [ ] axe reports no violations on every page; keyboard-only navigation works.
- [ ] Draft content never appears on the site (tested at build time).

**Prompt**
> Milestone M4. Branch `m4-site`. Build the design tokens and pages in docs/architecture.md
> sections 1 and 2. Show me screenshots of the home and a fictional project page in light and dark
> themes, on desktop and mobile, in the pull request.

---

## M5: Chat panel, evidence rail, transparency and recruiter mode

**Goal:** the interactive heart of the site.

**Scope:** chat panel consuming SSE; streaming answer with citation chips; evidence rail (side on
desktop, bottom sheet on mobile); transparency drawer (chunks, scores, method, timings, citation
checks); session history; "Ask about this project"; recruiter mode picker driving starter questions
and project ordering; pre-generated starter answers served without a model call; `/ask`; waking,
rate-limited, no-evidence and offline states; `/health` warm-up on page load.

**Acceptance criteria**
- [ ] Screen readers get polite announcements per sentence or on completion, not per token.
- [ ] Citation chips are links with descriptive names; hover or focus highlights the evidence card.
- [ ] Playwright tests cover streaming, citations, no-evidence and error states against a mocked API.

**Prompt**
> Milestone M5. Branch `m5-chat-ui`. Build the chat experience described in docs/architecture.md
> sections 1, 2 and 6, against a mocked SSE API. Keep the role out of chat requests. Include a short
> screen recording or screenshots of a cited answer and the transparency drawer in the pull request.

---

## M6: Deployment, domain and monitoring

**Goal:** the site is live and protected.

**Scope:** Cloud Run Dockerfile and deploy workflow (scale to zero, max instances capped); Vercel
project configuration; migrations in the deploy workflow; `ingest` workflow with the evaluation
gate; Cloudflare Turnstile keys; CORS for the production domain; budget alert instructions in the
README; a minimal internal cost and latency report from `query_logs`.

**Acceptance criteria**
- [ ] A merge to `main` deploys web and api; a content change creates and activates a new index.
- [ ] Secrets only in platform secret stores; README lists which secret goes where.
- [ ] A runbook in `docs/runbook.md`: rollback an index, rotate keys, pause chat.

**Prompt**
> Milestone M6. Branch `m6-deploy`. Write the deployment and ingest workflows and the runbook per
> docs/architecture.md sections 3, 7 and 9. Do not create cloud resources yourself; list the
> manual steps Michael must do (accounts, secrets, domain DNS) in the pull request.

---

## M7: Generation evaluation and wave 1 launch

**Goal:** evidence that answers are grounded, then launch.

**Scope:** generation evaluation runner (citation validity, groundedness and required facts with
Claude Opus 5.5 as judge, refusal correctness, latency, cost); `eval-generation` workflow on demand;
recruiter-mode consistency check; first baseline written to `evals/baselines/`; launch checklist.

**Acceptance criteria**
- [ ] Evaluation runs only when triggered and prints its estimated cost before running.
- [ ] Every distinction check and adversarial question passes, or the failures are listed.
- [ ] Baseline committed; thresholds proposed for Michael's approval.

**Prompt**
> Milestone M7. Branch `m7-evals`. Build the generation evaluation per docs/architecture.md
> section 8. Before running it against a paid model, show me the estimated cost and wait for my yes.

---

## M8: Wave 2, knowledge graph and How it works

**Goal:** the explorable graph and the public explanation of the system.

**Scope:** graph built from frontmatter tags at ingestion (`entities`, `entity_links`);
`GET /v1/graph`; `/explore` with a visual graph and an equivalent accessible list view; selecting a
node filters projects and seeds the chat; `/how-it-works` showing pipeline stages and
`GET /v1/eval/latest` results; semantic citation check; reranker experiment behind a flag with an
evaluation comparison.

**Acceptance criteria**
- [ ] Graph library loads only on `/explore`; the list view is fully keyboard accessible.
- [ ] Every edge points at an evidence chunk.
- [ ] Reranker is enabled only if the evaluation shows a gain; the decision is recorded in an ADR.

**Prompt**
> Milestone M8. Branch `m8-wave2`. Build the knowledge graph and How it works page per
> docs/architecture.md sections 2, 5 and 6, then run the reranker experiment and write up the result
> as an ADR.
