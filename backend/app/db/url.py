"""Turn the configured DATABASE_URL into a SQLAlchemy async URL without leaking secrets."""

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

ASYNC_DRIVER = "postgresql+psycopg"

# Schemes users may paste (Tiger Data shows `postgres://...`); all map to psycopg 3.
_ACCEPTED_DRIVERS = {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg_async"}


class InvalidDatabaseUrlError(ValueError):
    """DATABASE_URL could not be parsed. The message never contains the URL itself."""


def to_async_url(raw_url: str) -> URL:
    """Parse ``raw_url`` and force the async psycopg 3 driver.

    Raises InvalidDatabaseUrlError with a secret-free message on bad input.
    """
    try:
        url = make_url(raw_url.strip())
    except ArgumentError:
        # SQLAlchemy's own message echoes the full URL, password included.
        raise InvalidDatabaseUrlError("DATABASE_URL is not a valid database URL.") from None

    if url.drivername not in _ACCEPTED_DRIVERS:
        raise InvalidDatabaseUrlError(
            "DATABASE_URL must be a PostgreSQL URL "
            "(postgres://, postgresql:// or postgresql+psycopg://)."
        )
    if not url.host or not url.database:
        raise InvalidDatabaseUrlError("DATABASE_URL must include a host and a database name.")

    return url.set(drivername=ASYNC_DRIVER)


def describe_url(url: URL) -> str:
    """Secret-free description for logs: driver and database name only."""
    return f"{url.drivername} database '{url.database}'"
