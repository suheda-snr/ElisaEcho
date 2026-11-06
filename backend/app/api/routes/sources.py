from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, PaginationDep, require_development
from app.schemas.common import Page
from app.schemas.sources import SourceCreate, SourceRead
from app.services import sources as service

router = APIRouter(prefix="/sources", tags=["communication sources"])


@router.get("", response_model=Page[SourceRead], summary="List communication sources")
async def list_sources(session: DbSession, page: PaginationDep) -> Page[SourceRead]:
    items, total = await service.list_sources(session, limit=page.limit, offset=page.offset)
    return Page[SourceRead](
        items=[SourceRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a communication source (development only)",
    dependencies=[Depends(require_development)],
    responses={
        403: {"description": "Not available outside development"},
        409: {"description": "Source already exists"},
    },
)
async def create_source(data: SourceCreate, session: DbSession) -> SourceRead:
    """Registers a source. It does not ingest messages and no connector is started."""
    try:
        source = await service.create_source(session, data)
    except service.SourceAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this source_type and external_source_id already exists.",
        ) from None
    return SourceRead.model_validate(source)
