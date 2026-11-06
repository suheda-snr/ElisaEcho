"""Model relationships and constraints against a real PostgreSQL + pgvector database."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    EMBEDDING_DIMENSION,
    CommunicationSource,
    ConversationThread,
    Equipment,
    Incident,
    KnowledgeCandidate,
    KnowledgeChunk,
    KnowledgeEvidence,
    KnowledgeItem,
    Message,
)
from app.models.enums import (
    ApprovalStatus,
    DetectionStatus,
    EvidenceType,
    ResolutionStatus,
    SourceType,
    ThreadProcessingStatus,
)

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


async def _thread(session: AsyncSession, suffix: str = "a") -> ConversationThread:
    source = CommunicationSource(
        name=f"Test source {suffix}", source_type=SourceType.SIMULATED, external_source_id=f"src-{suffix}"
    )
    thread = ConversationThread(source=source, external_thread_id=f"thr-{suffix}", title="Test thread")
    session.add(thread)
    await session.flush()
    return thread


def _msg(thread: ConversationThread, n: int, minutes: int, content: str = "text") -> Message:
    return Message(
        thread=thread,
        external_message_id=f"m{n}",
        author_external_id="u1",
        content=content,
        sent_at=T0 + timedelta(minutes=minutes),
    )


async def test_defaults_are_applied(db_session: AsyncSession) -> None:
    thread = await _thread(db_session)
    source = thread.source
    await db_session.refresh(thread)
    await db_session.refresh(source)
    assert thread.processing_status is ThreadProcessingStatus.PENDING
    assert thread.created_at.tzinfo is not None
    assert source.enabled is True


async def test_full_knowledge_graph_round_trip(db_session: AsyncSession) -> None:
    thread = await _thread(db_session)
    report = _msg(thread, 1, 0, "Site 42 keeps dropping connections")
    fix = _msg(thread, 2, 5, "Restart the affected service instead")
    confirm = _msg(thread, 3, 10, "That worked")
    candidate = KnowledgeCandidate(
        thread=thread,
        candidate_type="troubleshooting_resolution",
        title="Restart service instead of router",
        confidence=0.92,
        extracted_data={"steps": ["restart service"]},
        model_name="test-model",
    )
    item = KnowledgeItem(
        candidate=candidate,
        title="Restart the affected service, not the router",
        problem_description="Intermittent connectivity at Site 42",
        symptoms=["connections drop every 20-30 minutes"],
        attempted_actions=[{"action": "router reboot", "outcome": "temporary"}],
        applicability_conditions=["S42 router family"],
        resolution="Restart the DHCP relay service",
        resolution_status=ResolutionStatus.CONFIRMED_IN_CONVERSATION,
    )
    item.evidence = [
        KnowledgeEvidence(message=report, evidence_type=EvidenceType.PROBLEM_REPORT),
        KnowledgeEvidence(message=fix, evidence_type=EvidenceType.SUGGESTED_SOLUTION),
        KnowledgeEvidence(message=confirm, evidence_type=EvidenceType.CONFIRMED_RESOLUTION),
    ]
    item.equipment = [Equipment(equipment_identifier="TEST-RTR-01", site_identifier="S42")]
    item.incidents = [Incident(incident_number="TEST-INC-1", title="Site 42 outage")]
    item.chunks = [
        KnowledgeChunk(content="chunk without embedding yet", chunk_index=0),
        KnowledgeChunk(content="embedded chunk", chunk_index=1, embedding=[0.01] * EMBEDDING_DIMENSION),
    ]
    db_session.add_all([confirm, fix, report, item])
    await db_session.commit()
    db_session.expunge_all()

    loaded = await db_session.scalar(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item.id)
        .options(
            selectinload(KnowledgeItem.evidence).selectinload(KnowledgeEvidence.message),
            selectinload(KnowledgeItem.candidate).selectinload(KnowledgeCandidate.thread),
            selectinload(KnowledgeItem.equipment),
            selectinload(KnowledgeItem.incidents),
            selectinload(KnowledgeItem.chunks),
        )
    )
    assert loaded is not None
    # Confirmed in conversation, but NOT automatically an approved procedure.
    assert loaded.resolution_status is ResolutionStatus.CONFIRMED_IN_CONVERSATION
    assert loaded.approval_status is ApprovalStatus.UNREVIEWED
    assert loaded.candidate.detection_status is DetectionStatus.DETECTED
    assert loaded.candidate.thread.id == thread.id
    assert {e.message.content for e in loaded.evidence} == {
        "Site 42 keeps dropping connections",
        "Restart the affected service instead",
        "That worked",
    }
    assert [e.equipment_identifier for e in loaded.equipment] == ["TEST-RTR-01"]
    assert [i.incident_number for i in loaded.incidents] == ["TEST-INC-1"]
    assert [c.chunk_index for c in loaded.chunks] == [0, 1]
    assert loaded.chunks[0].embedding is None
    assert len(loaded.chunks[1].embedding) == EMBEDDING_DIMENSION


async def test_thread_messages_keep_original_order(db_session: AsyncSession) -> None:
    thread = await _thread(db_session)
    # Inserted out of order on purpose.
    db_session.add_all([_msg(thread, 3, 20), _msg(thread, 1, 0), _msg(thread, 2, 10)])
    await db_session.commit()
    db_session.expunge_all()

    loaded = await db_session.scalar(
        select(ConversationThread)
        .where(ConversationThread.id == thread.id)
        .options(selectinload(ConversationThread.messages))
    )
    assert [m.external_message_id for m in loaded.messages] == ["m1", "m2", "m3"]


async def test_cited_message_cannot_be_deleted(db_session: AsyncSession) -> None:
    thread = await _thread(db_session)
    message = _msg(thread, 1, 0)
    item = KnowledgeItem(title="t", problem_description="p")
    item.evidence = [KnowledgeEvidence(message=message, evidence_type=EvidenceType.PROBLEM_REPORT)]
    db_session.add(item)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(text("DELETE FROM messages WHERE id = :id"), {"id": message.id})


async def test_duplicate_equipment_identifier_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(Equipment(equipment_identifier="TEST-DUP-1"))
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(Equipment(equipment_identifier="TEST-DUP-1"))
            await db_session.flush()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE knowledge_candidates SET confidence = 1.5 WHERE id = :id",
        "UPDATE knowledge_candidates SET detection_status = 'maybe' WHERE id = :id",
    ],
)
async def test_check_constraints_are_enforced(db_session: AsyncSession, sql: str) -> None:
    thread = await _thread(db_session)
    candidate = KnowledgeCandidate(thread=thread, candidate_type="x", title="t")
    db_session.add(candidate)
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(text(sql), {"id": candidate.id})


async def test_embedding_dimension_is_enforced(db_session: AsyncSession) -> None:
    item = KnowledgeItem(title="t", problem_description="p")
    db_session.add(item)
    await db_session.flush()
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            db_session.add(KnowledgeChunk(knowledge_item=item, content="c", chunk_index=0, embedding=[0.1] * 3))
            await db_session.flush()


async def test_pgvector_extension_and_hnsw_index_exist(db_session: AsyncSession) -> None:
    assert await db_session.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")) == 1
    index_def = await db_session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_knowledge_chunks_embedding_hnsw'")
    )
    assert "hnsw" in index_def and "vector_cosine_ops" in index_def
