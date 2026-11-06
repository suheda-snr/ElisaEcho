"""Integration fixtures for an ISOLATED PostgreSQL test database.

Safety:
- Runs only when TEST_DATABASE_URL is set; otherwise all integration tests are skipped.
- The database name must contain "test" and must differ from backend/.env's DATABASE_URL,
  so the shared Tiger Data database can never be targeted by accident.
- The schema is rebuilt with Alembic (downgrade base -> upgrade head) once per run,
  and every test runs inside a transaction that is rolled back afterwards.
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import engine_provider
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.db.url import to_async_url
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _test_database_url() -> URL:
    raw = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not raw:
        pytest.skip("TEST_DATABASE_URL is not set; skipping database integration tests.")

    url = to_async_url(raw)
    if "test" not in (url.database or "").lower():
        pytest.exit(
            "Refusing to run: TEST_DATABASE_URL must point to a database whose name contains "
            "'test'. Integration tests rebuild the schema and must never run against a shared "
            "database.",
            returncode=2,
        )

    configured = dotenv_values(BACKEND_DIR / ".env").get("DATABASE_URL")
    if configured:
        app_url = to_async_url(configured)
        if (app_url.host, app_url.port, app_url.database) == (url.host, url.port, url.database):
            pytest.exit("Refusing to run: TEST_DATABASE_URL equals DATABASE_URL.", returncode=2)
    return url


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(pytest.mark.integration)


def _alembic(*args: str, url: URL) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "ENVIRONMENT": "test",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic {' '.join(args)} failed:\n{result.stderr[-2000:]}")


@pytest.fixture(scope="session")
def test_db_url() -> URL:
    url = _test_database_url()
    # Exercise both migration directions on the isolated database.
    _alembic("downgrade", "base", url=url)
    _alembic("upgrade", "head", url=url)
    return url


@pytest.fixture(scope="session")
async def engine(test_db_url: URL) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_db_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session inside an outer transaction that is always rolled back.

    Code under test may call commit(); with `create_savepoint` that only releases
    a savepoint, so nothing persists between tests.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(_env_file=None, environment="test")


@pytest.fixture
async def api(
    db_session: AsyncSession, engine: AsyncEngine, test_settings: Settings
) -> AsyncIterator[httpx.AsyncClient]:
    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[engine_provider] = lambda: (lambda: engine)
    app.dependency_overrides[get_settings] = lambda: test_settings
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
