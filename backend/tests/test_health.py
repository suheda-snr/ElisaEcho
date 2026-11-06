"""Health endpoints without a working database."""

import httpx
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.deps import engine_provider
from app.db.url import InvalidDatabaseUrlError
from app.main import app

PASSWORD = "n0t-a-real-Password"


async def test_api_health_is_independent_of_the_database(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Elisa Echo API"}


async def test_db_health_reports_not_configured(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health/db")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "not_configured"


async def test_db_health_reports_misconfigured_url(client: httpx.AsyncClient) -> None:
    def broken():
        raise InvalidDatabaseUrlError("DATABASE_URL is not a valid database URL.")

    app.dependency_overrides[engine_provider] = lambda: broken
    response = await client.get("/api/health/db")
    assert response.status_code == 503
    assert response.json()["database"] == "misconfigured"


async def test_db_health_reports_unreachable_without_leaking_secrets(
    client: httpx.AsyncClient,
) -> None:
    # Port 1 on localhost refuses connections immediately.
    engine = create_async_engine(
        f"postgresql+psycopg://admin:{PASSWORD}@127.0.0.1:1/tsdb",
        connect_args={"connect_timeout": 2},
    )
    app.dependency_overrides[engine_provider] = lambda: (lambda: engine)
    try:
        response = await client.get("/api/health/db")
    finally:
        await engine.dispose()

    assert response.status_code == 503
    body = response.json()
    assert body["database"] == "unreachable"
    assert PASSWORD not in response.text
    assert "127.0.0.1" not in response.text
    assert "admin" not in response.text


async def test_data_endpoints_return_503_when_database_not_configured(
    client: httpx.AsyncClient,
) -> None:
    for path in ("/api/sources", "/api/threads", "/api/knowledge"):
        response = await client.get(path)
        assert response.status_code == 503, path
        assert "DATABASE_URL" in response.json()["detail"]
