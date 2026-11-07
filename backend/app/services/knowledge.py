import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import KnowledgeEvidence, KnowledgeItem
from app.models.enums import ApprovalStatus, ResolutionStatus
from app.schemas.knowledge import DiscoveryInfo


async def list_knowledge_items(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    resolution_status: ResolutionStatus | None = None,
    approval_status: ApprovalStatus | None = None,
) -> tuple[list[KnowledgeItem], int]:
    query: Select = select(KnowledgeItem)
    if resolution_status is not None:
        query = query.where(KnowledgeItem.resolution_status == resolution_status)
    if approval_status is not None:
        query = query.where(KnowledgeItem.approval_status == approval_status)

    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await session.scalars(
        query.order_by(KnowledgeItem.created_at.desc(), KnowledgeItem.id).limit(limit).offset(offset)
    )
    return list(result), total


async def get_knowledge_item(session: AsyncSession, item_id: uuid.UUID) -> KnowledgeItem | None:
    return await session.scalar(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .options(
            selectinload(KnowledgeItem.evidence).selectinload(KnowledgeEvidence.message),
            selectinload(KnowledgeItem.equipment),
            selectinload(KnowledgeItem.incidents),
            selectinload(KnowledgeItem.candidate),
        )
    )


def discovery_info(item: KnowledgeItem) -> DiscoveryInfo | None:
    candidate = item.candidate
    if candidate is None:
        return None
    data = candidate.extracted_data or {}
    return DiscoveryInfo(
        thread_id=candidate.thread_id,
        classification=candidate.candidate_type,
        detection_status=candidate.detection_status.value,
        model_name=candidate.model_name,
        model_confidence=candidate.confidence,
        analyzed_at=data.get("analyzed_at"),
        missing_information=data.get("analysis", {}).get("missing_information", []),
        validation_flags=data.get("validation", {}).get("flags", []),
    )
