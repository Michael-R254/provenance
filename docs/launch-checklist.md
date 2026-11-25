# Wave 1 launch checklist

Tick each item only after checking it. Items marked (Michael) need Michael; the rest can be
done together.

## Content

- [ ] (Michael) At least one project write-up in `content/projects/` with `status: approved`
      and `permission` filled in.
- [ ] (Michael) `content/profile.md` written and approved.
- [ ] (Michael) Every guardrail written for projects with a distinction to keep (for example,
      TrapTracker: deterministic retrieval and constrained generation, not external RAG).
- [ ] (Michael) Starter answers in `content/starters.yaml` reviewed and approved word for word.
- [ ] `uv run --project ingest python -m ingest validate` reports no errors.

## Evaluation

- [ ] (Michael) `evals/datasets/questions.yaml` written together against the real content,
      covering every category in architecture section 8.
- [ ] Retrieval baseline for real content committed as
      `evals/baselines/content-retrieval.json`. This switches on the ingest workflow's quality
      gate.
- [ ] Paid generation evaluation run on the fixture corpus; baseline committed.
- [ ] Paid generation evaluation run on the real content and question set; every distinction
      and adversarial question passes, or each failure is fixed or accepted by Michael.
- [ ] (Michael) Thresholds in `evals/thresholds.yaml` reviewed and set to `approved`.

## Platform (README "Deployment")

- [ ] (Michael) Accounts, secrets, variables and DNS from the M6 pull request in place.
- [ ] (Michael) Anthropic prepaid credit bought, auto-reload off.
- [ ] (Michael) Google Cloud budget alert created.
- [ ] `DEPLOY_ENABLED=true`; the deploy workflow is green; the ingest workflow activated an
      index from the real content.

## Production smoke test

- [ ] `https://<api>/health` answers; the site loads over HTTPS on the apex and `www`.
- [ ] A chat question gets a streamed answer with working citation links.
- [ ] A question with no evidence gets the "couldn't find anything" answer.
- [ ] Turnstile runs (network tab shows the challenge; no "development-token" in requests).
- [ ] Pause test: set the spend cap to 0 (runbook), see the "resting" message, set it back.
- [ ] A request from another origin is refused by CORS.
- [ ] No draft project appears anywhere on the site or in answers.
- [ ] `python -m provenance.report --days 1` shows the smoke-test questions and their cost.
- [ ] `rollback-index` run once with `list`.

## Accessibility and quality

- [ ] Keyboard-only pass through home, ask, a project page and the command palette.
- [ ] Screen reader pass on the chat (answer announced, citations named).
- [ ] Lighthouse on production: accessibility 100, performance 90 or more on mobile.

## Decisions before launch

- [ ] (Michael) How long `query_logs` keeps visitors' questions, and a short privacy note on
      the site saying questions are logged to improve the guide.
- [ ] (Michael) The production domain and the API hostname.
