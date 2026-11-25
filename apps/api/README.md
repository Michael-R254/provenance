# Provenance API

FastAPI service for retrieval and grounded, cited answers. See `../../docs/architecture.md`.

```bash
uv sync
uv run uvicorn provenance.main:app --reload
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```
