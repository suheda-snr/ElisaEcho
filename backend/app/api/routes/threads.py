import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, PaginationDep
from app.models.enums import ThreadProcessingStatus
from app.schemas.common import Page
from app.schemas.threads import MessageRead, ThreadDetail, ThreadRead
from app.services import threads as service

router = APIRouter(prefix="/threads", tags=["conversation threads"])

_NOT_FOUND = {404: {"description": "Thread not found"}}


@router.get("", response_model=Page[ThreadRead], summary="List conversation threads")
async def list_threads(
    session: DbSession,
    page: PaginationDep,
    source_id: uuid.UUID | None = None,
    processing_status: ThreadProcessingStatus | None = None,
) -> Page[ThreadRead]:
    items, total = await service.list_threads(
        session,
        limit=page.limit,
        offset=page.offset,
        source_id=source_id,
        processing_status=processing_status,
    )
    return Page[ThreadRead](
        items=[ThreadRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{thread_id}", response_model=ThreadDetail, summary="Get a thread", responses=_NOT_FOUND
)
async def get_thread(thread_id: uuid.UUID, session: DbSession) -> ThreadDetail:
    thread = await service.get_thread(session, thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    return ThreadDetail.model_validate(thread)


@router.get(
    "/{thread_id}/messages",
    response_model=Page[MessageRead],
    summary="List a thread's messages in original order",
    responses=_NOT_FOUND,
)
async def list_thread_messages(
    thread_id: uuid.UUID, session: DbSession, page: PaginationDep
) -> Page[MessageRead]:
    if not await service.thread_exists(session, thread_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    items, total = await service.list_messages(
        session, thread_id, limit=page.limit, offset=page.offset
    )
    return Page[MessageRead](
        items=[MessageRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
