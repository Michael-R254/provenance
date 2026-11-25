# Provenance API image for Google Cloud Run. Build from apps/api:
#   docker build -t provenance-api apps/api
# The embedding model is downloaded at build time so a cold start never fetches it.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    FASTEMBED_CACHE_PATH=/app/models
WORKDIR /app
# Dependencies first, so code changes reuse the cached layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable
RUN .venv/bin/python -c "from provenance.embedding import DEFAULT_MODEL; \
from fastembed import TextEmbedding; TextEmbedding(model_name=DEFAULT_MODEL)"

FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/models /app/models
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/models \
    HF_HUB_OFFLINE=1 \
    PROVENANCE_ENVIRONMENT=production \
    PORT=8080
USER app
EXPOSE 8080
# Cloud Run sets PORT. The API reads the client address from X-Forwarded-For itself.
CMD ["sh", "-c", "exec uvicorn provenance.main:app --host 0.0.0.0 --port \"$PORT\" --no-server-header --no-access-log"]
