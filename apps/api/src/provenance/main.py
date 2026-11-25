"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from provenance import __version__
from provenance.api import router
from provenance.config import Settings, get_settings
from provenance.services import Services, build_services

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    version: str


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    services = services or build_services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if services.database is not None:
            services.database.open()
        try:
            yield
        finally:
            if services.database is not None:
                services.database.close()

    app = FastAPI(
        title="Provenance API",
        version=__version__,
        lifespan=lifespan,
        # No public schema or docs in production: nothing internal to browse.
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    app.state.settings = settings
    app.state.services = services
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else "error"
        if exc.status_code == 503:
            code = "unavailable"
        return JSONResponse({"error": code}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field names only: no echo of the input, no internals.
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()})
        return JSONResponse({"error": "invalid_request", "fields": fields}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
