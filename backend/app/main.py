import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import DatabaseNotConfiguredError, dispose_engine
from app.db.url import InvalidDatabaseUrlError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


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

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
