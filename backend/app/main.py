import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiClient
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.db.session import DatabaseNotConfiguredError, dispose_engine, get_sessionmaker
from app.services.discovery.engine import DiscoveryEngine
from app.db.url import InvalidDatabaseUrlError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.discovery.shutdown()
    await dispose_engine()


def build_discovery_engine(settings: Settings, gemini: GeminiClient, embeddings: EmbeddingService) -> DiscoveryEngine:
    return DiscoveryEngine(
        session_factory=lambda: get_sessionmaker()(),
        gemini_factory=lambda: gemini,
        embedder_factory=lambda: embeddings,
        debounce_seconds=settings.discovery_debounce_seconds,
        message_interval_seconds=settings.simulation_message_interval_seconds,
        max_concurrent_analyses=settings.discovery_max_concurrent_analyses,
    )


def _unavailable(detail: str) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": detail})


def register_database_error_handlers(app: FastAPI) -> None:
    """Turn database problems into 503s without leaking connection details."""

    @app.exception_handler(DatabaseNotConfiguredError)
    async def not_configured(_: Request, __: DatabaseNotConfiguredError) -> JSONResponse:
        return _unavailable("Database is not configured. Set DATABASE_URL on the backend.")

    @app.exception_handler(InvalidDatabaseUrlError)
    async def invalid_url(_: Request, exc: InvalidDatabaseUrlError) -> JSONResponse:
        return _unavailable(str(exc))

    @app.exception_handler(OperationalError)
    async def operational(_: Request, exc: OperationalError) -> JSONResponse:
        logger.warning("Database operation failed: %s", type(exc.orig).__name__)
        return _unavailable("Database is unavailable.")

    @app.exception_handler(DBAPIError)
    async def dbapi(_: Request, exc: DBAPIError) -> JSONResponse:
        if exc.connection_invalidated:
            logger.warning("Database connection lost: %s", type(exc.orig).__name__)
            return _unavailable("Database is unavailable.")
        logger.error("Database error: %s", type(exc.orig).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal database error."},
        )


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Automatic discovery of operational knowledge from engineers' conversations.",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_database_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    # In-process discovery pipeline (development MVP; single backend process only).
    # One Gemini client per process (no network until first use), shared by analysis and search.
    gemini = GeminiClient.from_settings(settings)
    app.state.embeddings = EmbeddingService.from_settings(settings, gemini)
    app.state.discovery = build_discovery_engine(settings, gemini, app.state.embeddings)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
