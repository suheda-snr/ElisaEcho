"""Load guides and sessions with the evidence needed by the UI."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ConversationThread,
    GuideNode,
    KnowledgeItem,
    Message,
    NodeEvidence,
    TroubleshootingGuide,
    TroubleshootingSession,
)
from app.models.enums import GuideNodeType, SessionStepType
from app.schemas.guides import (
    GuideEdgeRead,
    GuideNodeRead,
    GuideRead,
    KnowledgeRef,
    NodeEvidenceRead,
    SessionRead,
    SessionStepRead,
)
from app.services.retrieval.results import MAX_EXCERPT_CHARS


async def load_guide(session: AsyncSession, guide_id: uuid.UUID) -> TroubleshootingGuide | None:
    return await session.scalar(
        select(TroubleshootingGuide)
        .where(TroubleshootingGuide.id == guide_id)
        .options(
            selectinload(TroubleshootingGuide.nodes).selectinload(GuideNode.evidence),
            selectinload(TroubleshootingGuide.edges),
        )
        .execution_options(populate_existing=True)
    )


def start_node(guide: TroubleshootingGuide) -> GuideNode | None:
    return next((n for n in guide.nodes if n.node_type is GuideNodeType.START), None)


def _excerpt(message: Message) -> str | None:
    if message.deleted_at is not None:
        return None
    text = message.content.strip()
    return text if len(text) <= MAX_EXCERPT_CHARS else text[: MAX_EXCERPT_CHARS - 1].rstrip() + "…"


async def guide_read(session: AsyncSession, guide: TroubleshootingGuide) -> GuideRead:
    message_ids = {e.message_id for n in guide.nodes for e in n.evidence}
    messages = {
        m.id: m
        for m in await session.scalars(
            select(Message)
            .where(Message.id.in_(message_ids))
            .options(selectinload(Message.thread).selectinload(ConversationThread.source))
        )
    } if message_ids else {}

    knowledge_ids = [uuid.UUID(k) for k in guide.source_knowledge_ids]
    items = {
        k.id: k
        for k in await session.scalars(
            select(KnowledgeItem)
            .where(KnowledgeItem.id.in_(knowledge_ids))
            .options(
                selectinload(KnowledgeItem.equipment),
                selectinload(KnowledgeItem.incidents),
                selectinload(KnowledgeItem.candidate),
            )
        )
    } if knowledge_ids else {}
    threads = {
        t.id: t
        for t in await session.scalars(
            select(ConversationThread)
            .where(ConversationThread.id.in_([k.candidate.thread_id for k in items.values() if k.candidate]))
            .options(selectinload(ConversationThread.source))
        )
    } if items else {}

    def evidence_read(e: NodeEvidence) -> NodeEvidenceRead:
        m = messages[e.message_id]
        source = m.thread.source
        return NodeEvidenceRead(
            message_id=m.id, knowledge_item_id=e.knowledge_item_id, evidence_type=e.evidence_type,
            author=m.author_display_name or m.author_external_id, sent_at=m.sent_at, excerpt=_excerpt(m),
            deleted_at_source=m.deleted_at is not None, source_name=source.name if source else None,
            source_type=source.source_type if source else None, thread_title=m.thread.title,
            source_url=m.source_url,
        )

    def knowledge_ref(k: KnowledgeItem) -> KnowledgeRef:
        thread = threads.get(k.candidate.thread_id) if k.candidate else None
        data = (k.candidate.extracted_data or {}) if k.candidate else {}
        return KnowledgeRef(
            id=k.id, title=k.title, problem_description=k.problem_description, resolution=k.resolution,
            resolution_status=k.resolution_status, approval_status=k.approval_status,
            applicability_conditions=k.applicability_conditions or [],
            missing_information=data.get("analysis", {}).get("missing_information", []),
            equipment_identifiers=sorted(e.equipment_identifier for e in k.equipment),
            incident_numbers=sorted(i.incident_number for i in k.incidents),
            conversation=thread.title if thread else None,
            source_name=thread.source.name if thread and thread.source else None,
        )

    start = start_node(guide)
    return GuideRead(
        id=guide.id, title=guide.title, problem_description=guide.problem_description,
        equipment_identifier=guide.equipment_identifier, status=guide.status, status_reason=guide.status_reason,
        summary=guide.summary, model_name=guide.model_name, created_at=guide.created_at,
        start_node_id=start.id if start else None,
        nodes=[
            GuideNodeRead(
                id=n.id, key=n.node_key, node_type=n.node_type, title=n.title, description=n.description,
                question=n.question, expected_answers=n.expected_answers,
                applicability_conditions=n.applicability_conditions,
                knowledge_item_ids=[uuid.UUID(k) for k in n.knowledge_item_ids],
                approval_status=n.approval_status, support_level=n.support_level,
                requires_manual_verification=n.requires_manual_verification, conflict_note=n.conflict_note,
                evidence=[evidence_read(e) for e in n.evidence if e.message_id in messages],
            )
            for n in guide.nodes
        ],
        edges=[
            GuideEdgeRead(id=e.id, source_node_id=e.source_node_id, target_node_id=e.target_node_id,
                          answer_label=e.answer_label, condition=e.condition)
            for e in guide.edges
        ],
        knowledge=[knowledge_ref(items[k]) for k in knowledge_ids if k in items],
        conflicts=guide.conflicts, uncertainties=guide.uncertainties, validation_notes=guide.validation_notes,
    )


async def load_session(session: AsyncSession, session_id: uuid.UUID) -> TroubleshootingSession | None:
    return await session.scalar(
        select(TroubleshootingSession)
        .where(TroubleshootingSession.id == session_id)
        .options(selectinload(TroubleshootingSession.steps))
        .execution_options(populate_existing=True)
    )


def active_path(ts: TroubleshootingSession, start_id: uuid.UUID | None) -> list[uuid.UUID]:
    path = [start_id] if start_id else []
    for step in ts.steps:
        if step.step_type is SessionStepType.ANSWER and not step.superseded and step.target_node_id:
            path.append(step.target_node_id)
    return path


def session_read(ts: TroubleshootingSession, start_id: uuid.UUID | None) -> SessionRead:
    return SessionRead(
        id=ts.id, guide_id=ts.guide_id, status=ts.status, current_node_id=ts.current_node_id,
        active_path=active_path(ts, start_id), outcome_summary=ts.outcome_summary,
        action_taken=ts.action_taken, created_at=ts.created_at, updated_at=ts.updated_at,
        completed_at=ts.completed_at,
        steps=[SessionStepRead.model_validate(s, from_attributes=True) for s in ts.steps],
    )

