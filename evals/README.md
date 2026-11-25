# Provenance evaluation

Measures retrieval quality (and, from M7, answer quality). See `../docs/architecture.md` section 8.

- `datasets/fixture.yaml`: questions over the fictional corpus in `fixtures/content` (CI gate).
- `datasets/questions.yaml`: the real question set, written with Michael (added with real content).
- `baselines/`: stored metrics; CI fails if hybrid recall@k or MRR drops below them.

```bash
uv sync
export PROVENANCE_TEST_DATABASE_URL=postgresql://provenance:provenance-local-only@localhost:5432/provenance_test
uv run python -m evals.retrieval --reset-database                        # gated, fake embedder
uv run python -m evals.retrieval --reset-database --embedder fastembed --no-baseline
uv run python -m evals.retrieval --reset-database --update-baseline      # after a deliberate change
```

`--reset-database` is required because the runner wipes the target database before indexing.
