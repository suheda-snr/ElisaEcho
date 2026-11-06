"""Shared FastAPI dependencies."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db, get_engine

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50

DbSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def engine_provider() -> Callable[[], AsyncEngine]:
    """Indirection so tests can substitute the engine used by the DB health check."""
    return get_engine


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size")] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=1_000_000, description="Items to skip")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(pagination)]


def require_development(settings: SettingsDep) -> None:
    """Block write endpoints outside development/test until authentication exists."""
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in development.",
        )
