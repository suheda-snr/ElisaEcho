"""Read models for the Live Discovery page and the Dashboard."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommunicationSource, ConversationThread, KnowledgeCandidate, KnowledgeItem, Message
from app.models.enums import DetectionStatus, ResolutionStatus, ThreadProcessingStatus
from app.schemas.discovery import CandidateSummary, DiscoveryMetrics, ThreadDiscovery
from app.services.threads import list_threads


async def discovery_metrics(session: AsyncSession) -> DiscoveryMetrics:
    async def count(stmt) -> int:
        return int(await session.scalar(stmt) or 0)

    thread_status = func.count().filter
    row = (
        await session.execute(
            select(
                func.count(),
                thread_status(ConversationThread.processing_status == ThreadProcessingStatus.PROCESSED),
                thread_status(ConversationThread.processing_status == ThreadProcessingStatus.FAILED),
                thread_status(ConversationThread.processing_status.in_(
                    [ThreadProcessingStatus.PENDING, ThreadProcessingStatus.PROCESSING])),
            ).select_from(ConversationThread)
        )
    ).one()
    candidate_status = func.count().filter
    candidates = (
        await session.execute(
            select(
                candidate_status(KnowledgeCandidate.detection_status != DetectionStatus.REJECTED),
                candidate_status(KnowledgeCandidate.detection_status == DetectionStatus.REJECTED),
            ).select_from(KnowledgeCandidate)
        )
    ).one()
    return DiscoveryMetrics(
        messages_processed=await count(select(func.count()).select_from(Message)),
        threads_total=row[0],
        threads_analyzed=row[1],
        threads_failed=row[2],
        threads_pending=row[3],
        candidates_detected=candidates[0],
        conversations_ignored=candidates[1],
        knowledge_items=await count(select(func.count()).select_from(KnowledgeItem)),
        confirmed_resolutions=await count(
            select(func.count()).select_from(KnowledgeItem).where(
                KnowledgeItem.resolution_status == ResolutionStatus.CONFIRMED_IN_CONVERSATION)
        ),
        unverified_suggestions=await count(
            select(func.count()).select_from(KnowledgeItem).where(
                KnowledgeItem.resolution_status == ResolutionStatus.SUGGESTED)
        ),
    )


async def thread_discoveries(
    session: AsyncSession, *, limit: int, offset: int, source_id: uuid.UUID | None = None
) -> tuple[list[ThreadDiscovery], int]:
    threads, total = await list_threads(session, limit=limit, offset=offset, source_id=source_id)
    if not threads:
        return [], total

    candidates = list(
        await session.scalars(
            select(KnowledgeCandidate)
            .where(KnowledgeCandidate.thread_id.in_([t.id for t in threads]))
            .order_by(KnowledgeCandidate.created_at)
        )
    )
    items = {
        item.candidate_id: item
        for item in await session.scalars(
            select(KnowledgeItem).where(KnowledgeItem.candidate_id.in_([c.id for c in candidates]))
        )
    } if candidates else {}

    sources = {
        src.id: src
        for src in await session.scalars(
            select(CommunicationSource).where(
                CommunicationSource.id.in_({t.communication_source_id for t in threads}))
        )
    }

    by_thread: dict[uuid.UUID, KnowledgeCandidate] = {}
    for candidate in candidates:
        by_thread.setdefault(candidate.thread_id, candidate)

    result = []
    for thread in threads:
        candidate = by_thread.get(thread.id)
        summary = None
        if candidate is not None:
            item = items.get(candidate.id)
            data = candidate.extracted_data or {}
            summary = CandidateSummary(
                id=candidate.id,
                classification=candidate.candidate_type,
                detection_status=candidate.detection_status,
                title=candidate.title,
                summary=candidate.summary,
                confidence=candidate.confidence,
                model_name=candidate.model_name,
                analyzed_at=data.get("analyzed_at"),
                analyzed_message_count=len(data.get("analyzed_message_ids", [])),
                flags=data.get("validation", {}).get("flags", []),
                knowledge_item_id=item.id if item else None,
                resolution_status=item.resolution_status if item else None,
                approval_status=item.approval_status if item else None,
            )
        result.append(ThreadDiscovery(
            id=thread.id,
            title=thread.title,
            external_thread_id=thread.external_thread_id,
            source_name=sources[thread.communication_source_id].name if thread.communication_source_id in sources else None,
            source_type=sources[thread.communication_source_id].source_type if thread.communication_source_id in sources else None,
            processing_status=thread.processing_status,
            message_count=thread.message_count,
            last_message_at=thread.last_message_at,
            candidate=summary,
        ))
    return result, total
