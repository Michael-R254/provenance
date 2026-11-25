# Provenance ingestion

Turns approved Markdown in `content/` into a versioned, searchable index (pgvector + full-text).
See `../docs/architecture.md` section 4 and `../docs/decisions/0002-chunking-and-anchors.md`.

```bash
uv sync
uv run python -m ingest validate                      # check content, write nothing
uv run python -m ingest run --dry-run                 # validate + chunk summary
uv run python -m ingest migrate                       # needs PROVENANCE_DATABASE_URL
uv run python -m ingest run --activate                # build and activate a new index version
uv run python -m ingest activate <version>            # roll back to an earlier version
```

Tests: `uv run pytest`. Integration tests need Postgres:
`PROVENANCE_TEST_DATABASE_URL=postgresql://provenance:provenance-local-only@localhost:5432/provenance_test`.
