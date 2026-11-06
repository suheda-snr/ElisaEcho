"""Shared test setup.

Unit tests never touch a database: DATABASE_URL is forced empty below, so even a
real backend/.env (e.g. with Tiger Data credentials) is ignored during tests.
Integration tests use TEST_DATABASE_URL only (see tests/integration/conftest.py).
"""

import os

# Must run before any `app` import reads settings. Environment variables take
# precedence over backend/.env in pydantic-settings.
os.environ["DATABASE_URL"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["GEMINI_API_KEY"] = ""

from collections.abc import AsyncIterator, Iterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Client against the real app wiring, without a database."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def client_without_db_access() -> AsyncIterator[httpx.AsyncClient]:
    """Client whose DB session is a stub, for request-validation tests.

    Any attempt to actually use the session fails the test.
    """

    class _UnusableSession:
        def __getattr__(self, name: str):
            raise AssertionError(f"Validation test unexpectedly used the database ({name}).")

    async def _stub_db():
        yield _UnusableSession()

    app.dependency_overrides[get_db] = _stub_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
