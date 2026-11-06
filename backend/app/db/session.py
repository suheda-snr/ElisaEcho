"""Async SQLAlchemy engine and session management.

The engine is created lazily on first use, so the API starts (and /api/health
works) even when DATABASE_URL is missing or the database is down.
"""

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.url import describe_url, to_async_url

logger = logging.getLogger(__name__)


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL is not set."""


def create_engine_from_settings(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL is not set.")

    url = to_async_url(settings.database_url.get_secret_value())
    logger.info("Creating database engine for %s", describe_url(url))

    return create_async_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the shared engine, creating it on first call."""
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_engine_from_settings(get_settings())
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session; commits are left to the caller."""
    async with get_sessionmaker()() as session:
        yield session
