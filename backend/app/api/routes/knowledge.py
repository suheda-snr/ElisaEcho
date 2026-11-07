import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, PaginationDep
from app.models.enums import ApprovalStatus, ResolutionStatus
from app.schemas.common import Page
from app.schemas.knowledge import KnowledgeItemDetail, KnowledgeItemSummary
from app.services import knowledge as service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=Page[KnowledgeItemSummary], summary="List knowledge items")
async def list_knowledge(
    session: DbSession,
    page: PaginationDep,
    resolution_status: ResolutionStatus | None = None,
    approval_status: ApprovalStatus | None = None,
) -> Page[KnowledgeItemSummary]:
    items, total = await service.list_knowledge_items(
        session,
        limit=page.limit,
        offset=page.offset,
        resolution_status=resolution_status,
        approval_status=approval_status,
    )
    return Page[KnowledgeItemSummary](
        items=[KnowledgeItemSummary.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{item_id}",
    response_model=KnowledgeItemDetail,
    summary="Get a knowledge item with its evidence",
    responses={404: {"description": "Knowledge item not found"}},
)
async def get_knowledge(item_id: uuid.UUID, session: DbSession) -> KnowledgeItemDetail:
    item = await service.get_knowledge_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found.")
    detail = KnowledgeItemDetail.model_validate(item)
    detail.discovery = service.discovery_info(item)
    return detail
