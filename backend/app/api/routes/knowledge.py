import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, PaginationDep
from app.models.enums import ApprovalStatus, ResolutionStatus
from app.schemas.common import Page
from app.schemas.consolidation import RelatedKnowledge
from app.schemas.knowledge import KnowledgeItemDetail, KnowledgeItemSummary
from app.services import knowledge as service
from app.services.consolidation import queries as consolidation

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
    summaries = []
    for item in items:
        summary = KnowledgeItemSummary.model_validate(item)
        thread = item.candidate.thread if item.candidate else None
        if thread is not None:
            summary.conversation = thread.title
            summary.source_type = thread.source.source_type.value if thread.source else None
            summary.source_name = thread.source.name if thread.source else None
        summaries.append(summary)
    return Page[KnowledgeItemSummary](
        items=summaries,
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
    for name, value in (await service.context_fields(session, [item]))[item.id].items():
        setattr(detail, name, value)
    return detail


@router.get(
    "/{item_id}/related",
    response_model=RelatedKnowledge,
    summary="Related knowledge (AI-suggested relationships and group) for an item",
    responses={404: {"description": "Knowledge item not found or not visible"}},
)
async def get_related_knowledge(item_id: uuid.UUID, session: DbSession) -> RelatedKnowledge:
    related = await consolidation.related_knowledge(session, item_id)
    if related is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found.")
    return related
