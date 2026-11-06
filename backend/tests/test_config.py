"""Database configuration: URL handling, secrets and engine options."""

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.db.session import DatabaseNotConfiguredError, create_engine_from_settings
from app.db.url import InvalidDatabaseUrlError, describe_url, to_async_url

PASSWORD = "s3cr3t-Pa55word"


@pytest.mark.parametrize(
    "raw",
    [
        f"postgres://tsdbadmin:{PASSWORD}@abc.tsdb.cloud.example:34567/tsdb?sslmode=require",
        f"postgresql://tsdbadmin:{PASSWORD}@abc.tsdb.cloud.example:34567/tsdb?sslmode=require",
        f"postgresql+psycopg://tsdbadmin:{PASSWORD}@abc.tsdb.cloud.example:34567/tsdb?sslmode=require",
    ],
)
def test_urls_are_normalized_to_async_psycopg(raw: str) -> None:
    url = to_async_url(raw)
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "abc.tsdb.cloud.example"
    assert url.port == 34567
    assert url.database == "tsdb"
    assert url.query["sslmode"] == "require"


@pytest.mark.parametrize(
    "raw",
    [
        f"not a url {PASSWORD}",
        f"mysql://user:{PASSWORD}@host/db",
        f"postgresql://user:{PASSWORD}@/db",
        f"postgresql://user:{PASSWORD}@host",
    ],
)
def test_invalid_urls_raise_without_leaking_the_password(raw: str) -> None:
    with pytest.raises(InvalidDatabaseUrlError) as exc_info:
        to_async_url(raw)
    assert PASSWORD not in str(exc_info.value)
    assert exc_info.value.__cause__ is None  # original (leaky) error is suppressed


def test_describe_url_contains_no_credentials_or_host() -> None:
    url = to_async_url(f"postgres://admin:{PASSWORD}@secret-host.example:5432/tsdb")
    description = describe_url(url)
    assert PASSWORD not in description
    assert "admin" not in description
    assert "secret-host" not in description


def test_database_url_is_optional_and_empty_means_unset() -> None:
    assert Settings(_env_file=None).database_url is None
    assert Settings(_env_file=None, database_url="  ").database_url is None


def test_database_url_is_a_secret() -> None:
    settings = Settings(_env_file=None, database_url=f"postgres://u:{PASSWORD}@h:5432/db")
    assert isinstance(settings.database_url, SecretStr)
    assert PASSWORD not in repr(settings)
    assert PASSWORD not in str(settings.model_dump())


def test_environment_flags() -> None:
    assert Settings(_env_file=None, environment="Development").is_development
    assert Settings(_env_file=None, environment="test").is_development
    assert not Settings(_env_file=None, environment="production").is_development
    assert not Settings(_env_file=None, environment="staging").is_development


def test_cors_origins_are_split() -> None:
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test,")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_engine_requires_database_url() -> None:
    with pytest.raises(DatabaseNotConfiguredError):
        create_engine_from_settings(Settings(_env_file=None))


async def test_engine_uses_pooling_pre_ping_and_hides_password() -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"postgres://u:{PASSWORD}@db.example:5432/tsdb?sslmode=require",
        database_pool_size=3,
        database_max_overflow=2,
    )
    engine = create_engine_from_settings(settings)  # does not connect
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.pool._pre_ping is True
        assert engine.pool.size() == 3
        assert engine.pool._max_overflow == 2
        assert PASSWORD not in repr(engine)
        assert PASSWORD not in str(engine.url)
    finally:
        await engine.dispose()
