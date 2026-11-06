"""Database connectivity check used by GET /api/health/db."""

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import DatabaseNotConfiguredError
from app.db.url import InvalidDatabaseUrlError
from app.schemas.health import DatabaseHealthResponse

logger = logging.getLogger(__name__)

HEALTH_CHECK_TIMEOUT_SECONDS = 10
UNREACHABLE_DETAIL = (
    "Could not connect to the database. Check DATABASE_URL, network access "
    "and that the database service is running."
)


async def check_database(get_engine: Callable[[], AsyncEngine]) -> DatabaseHealthResponse:
    """Run `SELECT 1` and report pgvector availability. Never raises, never leaks secrets."""
    try:
        engine = get_engine()
    except DatabaseNotConfiguredError:
        return DatabaseHealthResponse(
            status="unavailable", database="not_configured", detail="DATABASE_URL is not set."
        )
    except InvalidDatabaseUrlError as exc:  # message is secret-free by construction
        return DatabaseHealthResponse(status="unavailable", database="misconfigured", detail=str(exc))

    try:
        async with asyncio.timeout(HEALTH_CHECK_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                has_pgvector = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                )
    except Exception as exc:  # noqa: BLE001 - any failure means "unreachable"
        # Log the exception type only: driver messages can include host names.
        logger.warning("Database health check failed: %s", type(exc).__name__)
        return DatabaseHealthResponse(
            status="unavailable", database="unreachable", detail=UNREACHABLE_DETAIL
        )

    return DatabaseHealthResponse(status="ok", database="connected", pgvector=bool(has_pgvector))
