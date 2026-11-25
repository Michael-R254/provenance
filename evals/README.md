# Provenance evaluation

Measures retrieval quality and answer quality. See `../docs/architecture.md` section 8 and
ADR 0008.

- `datasets/fixture.yaml`: retrieval questions over the fictional corpus in `fixtures/content`
  (CI gate).
- `datasets/fixture-generation.yaml`: generation questions over the same corpus, with required
  and forbidden facts, distinction checks, unanswerable and adversarial questions.
- `datasets/questions.yaml`: the real question set, written with Michael once real content
  exists. Never generated from the system's own answers.
- `rubrics/judge-v1.md`: the fixed rubric the judge (Claude Opus 5.5) grades with.
- `thresholds.yaml`: generation thresholds, `proposed` until Michael approves them.
- `baselines/`: stored metrics. CI fails if hybrid recall@k or MRR drops below the retrieval
  baseline.

## Retrieval

```bash
uv sync
export PROVENANCE_TEST_DATABASE_URL=postgresql://provenance:provenance-local-only@localhost:5432/provenance_test
uv run python -m evals.retrieval --reset-database                        # gated, fake embedder
uv run python -m evals.retrieval --reset-database --embedder fastembed --no-baseline
uv run python -m evals.retrieval --reset-database --update-baseline      # after a deliberate change
```

## Generation

Every question goes through the real API code (retrieval, evidence threshold, prompt, guardrails,
citation filter) in process, then a judge grades the answer.

```bash
# free: mock model, heuristic judge (also runs in CI)
uv run python -m evals.generation --reset-database

# paid: prints the estimate and stops; nothing is spent
uv run python -m evals.generation --reset-database --provider anthropic --judge anthropic

# paid: accept the estimate, never spend more than --max-cost, apply the release gate
ANTHROPIC_API_KEY=... uv run python -m evals.generation --reset-database \
  --provider anthropic --judge anthropic --max-cost 3 --yes --gate --update-baseline
```

Normally the paid run happens in the `eval-generation` workflow, which shows the estimate and
waits for approval before spending. `--reset-database` is required because both runners wipe the
target database before indexing.

What the gate enforces with `--gate`:

- always: every distinction question passes; no adversarial question makes an unsupported or
  forbidden claim or reveals its instructions; recruiter mode cannot change what the model is
  asked; the run finished every question.
- once `thresholds.yaml` says `status: approved`: the numeric thresholds in that file.
