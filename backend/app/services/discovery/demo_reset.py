"""Remove synthetic demo conversations and what was discovered from them.

Development-only (enforced by the route and here). Strictly scoped to threads of the
synthetic demo source; no other source, thread, message or knowledge is touched. The demo
source row itself is kept. Equipment/incident rows are shared reference data and are kept;
only their links to the removed knowledge items disappear.
"""

from dataclasses import dataclass

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    CommunicationSource,
    ConversationThread,
    GuideNode,
    KnowledgeCandidate,
    KnowledgeEvidence,
    KnowledgeItem,
    Message,
    NodeEvidence,
    TroubleshootingGuide,
)
from app.seed.demo_data import DEMO_SOURCE_EXTERNAL_ID, DEMO_SOURCE_TYPE
from app.seed.seed import SeedNotAllowedError, ensure_seed_allowed


@dataclass(frozen=True)
class ResetSummary:
    guides: int
    threads: int
    messages: int
    candidates: int
    knowledge_items: int


async def reset_demo_data(session: AsyncSession, settings: Settings) -> ResetSummary:
    """Caller commits."""
    try:
        ensure_seed_allowed(settings)
    except SeedNotAllowedError as exc:
        raise PermissionError(str(exc)) from None

    demo_threads = (
        select(ConversationThread.id)
        .join(CommunicationSource, ConversationThread.communication_source_id == CommunicationSource.id)
        .where(
            CommunicationSource.source_type == DEMO_SOURCE_TYPE,
            CommunicationSource.external_source_id == DEMO_SOURCE_EXTERNAL_ID,
        )
    )
    demo_candidates = select(KnowledgeCandidate.id).where(KnowledgeCandidate.thread_id.in_(demo_threads))
    demo_items = select(KnowledgeItem.id).where(KnowledgeItem.candidate_id.in_(demo_candidates))

    # Guides built from demo knowledge are derived demo data too. Deleting a guide cascades to
    # its nodes, edges, node evidence and sessions; guides from other knowledge are untouched.
    demo_messages = select(Message.id).where(Message.thread_id.in_(demo_threads))
    demo_guides = (
        select(GuideNode.guide_id)
        .join(NodeEvidence, NodeEvidence.node_id == GuideNode.id)
        .where(or_(NodeEvidence.message_id.in_(demo_messages), NodeEvidence.knowledge_item_id.in_(demo_items)))
    )
    guides = await session.execute(delete(TroubleshootingGuide).where(TroubleshootingGuide.id.in_(demo_guides)))

    # Order matters: evidence references messages (RESTRICT), items reference candidates.
    await session.execute(delete(KnowledgeEvidence).where(KnowledgeEvidence.knowledge_item_id.in_(demo_items)))
    items = await session.execute(delete(KnowledgeItem).where(KnowledgeItem.id.in_(demo_items)))
    candidates = await session.execute(delete(KnowledgeCandidate).where(KnowledgeCandidate.id.in_(demo_candidates)))
    messages = await session.execute(delete(Message).where(Message.thread_id.in_(demo_threads)))
    threads = await session.execute(delete(ConversationThread).where(ConversationThread.id.in_(demo_threads)))

    return ResetSummary(
        guides=guides.rowcount,
        threads=threads.rowcount,
        messages=messages.rowcount,
        candidates=candidates.rowcount,
        knowledge_items=items.rowcount,
    )
