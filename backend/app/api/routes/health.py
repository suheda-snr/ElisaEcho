from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import SettingsDep, engine_provider
from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.services.database import check_database
from app.services.health import get_health_status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="API health check")
def health(settings: SettingsDep) -> HealthResponse:
    """Always available; does not touch the database."""
    return get_health_status(settings)


@router.get(
    "/db",
    response_model=DatabaseHealthResponse,
    summary="Database connectivity check",
    responses={503: {"model": DatabaseHealthResponse, "description": "Database unavailable"}},
)
async def database_health(
    response: Response,
    get_engine: Annotated[Callable[[], AsyncEngine], Depends(engine_provider)],
) -> DatabaseHealthResponse:
    """Runs `SELECT 1` against PostgreSQL and reports whether pgvector is installed."""
    result = await check_database(get_engine)
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
