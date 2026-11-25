# 0003: Hybrid retrieval and its evaluation

- Status: accepted
- Date: 2026-11-25

## Context

The guide must find the right passage for both natural-language questions ("how did he test
it?") and exact terms (tool names, project names). It must stay cheap, readable and run inside
the one Postgres database.

## Decision

- **Two retrievers, one database.** pgvector cosine search over the HNSW index and Postgres
  full-text search, both scoped to the single active index version and an optional project.
- **Keyword search matches any term.** `plainto_tsquery` is rewritten from AND (`&`) to OR (`|`)
  and ranked with `ts_rank_cd`. With AND, a question had to contain every stemmed word of a
  passage's vocabulary to match at all; on the fixture set keyword recall@5 rose from 0.136 to
  0.697 after the change.
- **Fusion with RRF (k = 60)** over the top 20 candidates from each side; ties break on the best
  single rank, then chunk id, so results are deterministic.
- **Filtered vector search** uses `hnsw.iterative_scan = relaxed_order` (set per transaction) so a
  version or project filter cannot starve the result list.
- **Model mismatch is an error.** The API refuses to search an index whose `embedding_model`
  differs from its own embedder.
- **Embedder code is duplicated** in `ingest` and `apps/api` rather than shared through a third
  package; a parity test in `evals` fails if the two ever diverge.
- **Evaluation gate.** `evals/` indexes a fictional corpus, runs a fixed question set through
  every method and fails CI if hybrid recall@5 or MRR falls below the stored baseline. CI uses the
  deterministic fake embedder so the gate is stable; the real model is run on demand.

## Consequences

- The fixture baseline measures the pipeline, not real quality. Real numbers come from
  `datasets/questions.yaml` once Michael's content is approved.
- Under the fake embedder, hybrid currently equals vector; this is expected because the fake
  embedder is itself a bag of words. Fusion weights should be revisited with the real model.
- Changing chunking, fusion or the query form needs `--update-baseline` in the same pull request,
  with the reason stated.
