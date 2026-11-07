"""End-to-end discovery against the isolated test DB with a mocked Gemini."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import GeminiQuotaExceededError
from app.api.routes.discovery import get_discovery_engine
from app.core.config import Settings
from app.main import app
from app.models import (
    CommunicationSource,
    ConversationThread,
    Equipment,
    KnowledgeCandidate,
    KnowledgeEvidence,
    KnowledgeItem,
    Message,
)
from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    ResolutionStatus,
    SourceType,
    ThreadProcessingStatus,
)
from app.schemas.threads import MessageIngest, ThreadIngest
from app.seed.demo_data import DEMO_SOURCE_EXTERNAL_ID, DEMO_THREADS
from app.seed.seed import seed_demo_data
from app.services.discovery.analyzer import analyze_thread
from app.services.discovery.demo_reset import reset_demo_data
from app.services.discovery.engine import DiscoveryEngine
from app.services.ingestion import upsert_messages, upsert_source, upsert_thread
from tests.discovery_fakes import IRRELEVANT, FakeGemini, message_count, site42_confirmed, site42_suggested

SITE42 = next(t for t in DEMO_THREADS if t.scenario == "confirmed_resolution")
LUNCH = next(t for t in DEMO_THREADS if t.scenario == "irrelevant_chatter")


def site42_responder(contents: str):
    return site42_confirmed() if message_count(contents) >= 4 else site42_suggested()


async def _thread_id(session: AsyncSession, external_id: str) -> uuid.UUID:
    return await session.scalar(
        select(ConversationThread.id).where(ConversationThread.external_thread_id == external_id)
    )


async def _ingest_site42(session: AsyncSession, upto: int) -> uuid.UUID:
    """Deliver the first `upto` Site 42 messages, like the live feed would."""
    source_id = await upsert_source(session, name="Pipeline test", source_type=SourceType.SIMULATED,
                                    external_source_id="pipeline-test")
    thread_id = await upsert_thread(session, source_id, ThreadIngest(external_thread_id="pipe-site42",
                                                                     title=SITE42.title))
    await upsert_messages(session, thread_id, [
        MessageIngest(external_message_id=m.external_id, author_external_id=m.author_id,
                      author_display_name=m.author_name, content=m.content, sent_at=m.sent_at)
        for m in SITE42.messages[:upto]
    ])
    await session.commit()
    return thread_id


async def _counts(session: AsyncSession, thread_id: uuid.UUID) -> tuple[int, int, int]:
    candidates = await session.scalar(
        select(func.count()).select_from(KnowledgeCandidate).where(KnowledgeCandidate.thread_id == thread_id))
    items = await session.scalar(
        select(func.count()).select_from(KnowledgeItem).join(KnowledgeItem.candidate)
        .where(KnowledgeCandidate.thread_id == thread_id))
    evidence = await session.scalar(
        select(func.count()).select_from(KnowledgeEvidence).join(KnowledgeEvidence.knowledge_item)
        .join(KnowledgeItem.candidate).where(KnowledgeCandidate.thread_id == thread_id))
    return candidates, items, evidence


async def _item(session: AsyncSession, thread_id: uuid.UUID) -> KnowledgeItem:
    session.expunge_all()
    return await session.scalar(
        select(KnowledgeItem).join(KnowledgeItem.candidate).where(KnowledgeCandidate.thread_id == thread_id)
    )


async def test_confirmed_resolution_is_extracted_with_validated_evidence(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    outcome = await analyze_thread(db_session, thread_id, FakeGemini(site42_responder))

    assert outcome.status == "analyzed" and outcome.detection_status == "accepted"
    assert outcome.resolution_status == "confirmed_in_conversation"
    item = await _item(db_session, thread_id)
    assert item.resolution_status is ResolutionStatus.CONFIRMED_IN_CONVERSATION
    assert item.approval_status is ApprovalStatus.UNREVIEWED  # never auto-approved
    assert item.applicability_conditions == ["Do not reboot the whole router"]

    evidence = list(await db_session.scalars(
        select(KnowledgeEvidence).where(KnowledgeEvidence.knowledge_item_id == item.id)))
    messages = {m.id: m for m in await db_session.scalars(select(Message).where(Message.thread_id == thread_id))}
    assert all(e.message_id in messages for e in evidence)  # only messages of this thread
    confirming = [messages[e.message_id] for e in evidence if e.evidence_type is EvidenceType.CONFIRMED_RESOLUTION]
    assert [m.content for m in confirming] == [SITE42.messages[3].content]  # "That worked..."
    assert messages[confirming[0].id].sent_at == SITE42.messages[3].sent_at  # original preserved

    equipment = await db_session.scalar(select(Equipment).where(Equipment.equipment_identifier == "S42-RTR-01"))
    assert equipment is not None
    thread = await db_session.get(ConversationThread, thread_id)
    assert thread.processing_status is ThreadProcessingStatus.PROCESSED


async def test_unchanged_thread_is_not_sent_to_gemini_again(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    gemini = FakeGemini(site42_responder)
    await analyze_thread(db_session, thread_id, gemini)
    before = await _counts(db_session, thread_id)

    outcome = await analyze_thread(db_session, thread_id, gemini)
    assert outcome.status == "unchanged"
    assert len(gemini.calls) == 1
    assert await _counts(db_session, thread_id) == before


async def test_forced_reanalysis_is_idempotent(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    gemini = FakeGemini(site42_responder)
    first = await analyze_thread(db_session, thread_id, gemini)
    counts = await _counts(db_session, thread_id)
    second = await analyze_thread(db_session, thread_id, gemini, force=True)

    assert len(gemini.calls) == 2
    assert (second.candidate_id, second.knowledge_item_id) == (first.candidate_id, first.knowledge_item_id)
    assert await _counts(db_session, thread_id) == counts == (1, 1, counts[2])


async def test_thread_evolves_from_suggestion_to_confirmed_resolution(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=2)
    gemini = FakeGemini(site42_responder)
    first = await analyze_thread(db_session, thread_id, gemini)
    assert first.resolution_status == "suggested"
    early_evidence = {e.message_id for e in await db_session.scalars(
        select(KnowledgeEvidence).where(KnowledgeEvidence.knowledge_item_id == first.knowledge_item_id))}

    await _ingest_site42(db_session, upto=4)  # "Restarted..." and "That worked" arrive
    thread = await db_session.get(ConversationThread, thread_id, populate_existing=True)
    assert thread.processing_status is ThreadProcessingStatus.PENDING

    second = await analyze_thread(db_session, thread_id, gemini)
    assert second.status == "analyzed"
    assert second.knowledge_item_id == first.knowledge_item_id  # same item, updated
    assert second.resolution_status == "confirmed_in_conversation"
    assert await _counts(db_session, thread_id) == (1, 1, 4)
    late_evidence = {e.message_id for e in await db_session.scalars(
        select(KnowledgeEvidence).where(KnowledgeEvidence.knowledge_item_id == first.knowledge_item_id))}
    assert early_evidence <= late_evidence  # earlier supporting messages preserved


async def test_irrelevant_chatter_creates_no_knowledge(db_session: AsyncSession, test_settings: Settings) -> None:
    await seed_demo_data(db_session, test_settings)
    await db_session.commit()
    thread_id = await _thread_id(db_session, LUNCH.external_id)

    outcome = await analyze_thread(db_session, thread_id, FakeGemini(IRRELEVANT))
    assert outcome.detection_status == "rejected" and outcome.knowledge_item_id is None
    assert await _counts(db_session, thread_id) == (1, 0, 0)  # audit record only


async def test_gemini_failure_is_recorded_not_fabricated(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    outcome = await analyze_thread(db_session, thread_id, FakeGemini(GeminiQuotaExceededError("quota")))

    assert outcome.status == "failed" and "quota" in outcome.error
    assert await _counts(db_session, thread_id) == (0, 0, 0)
    thread = await db_session.get(ConversationThread, thread_id, populate_existing=True)
    assert thread.processing_status is ThreadProcessingStatus.FAILED

    # A later successful run recovers.
    recovered = await analyze_thread(db_session, thread_id, FakeGemini(site42_responder))
    assert recovered.status == "analyzed"


async def test_missing_api_key_leaves_thread_pending(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=2)
    gemini = FakeGemini(IRRELEVANT)
    gemini.configured = False
    outcome = await analyze_thread(db_session, thread_id, gemini)
    assert outcome.status == "not_configured" and gemini.calls == []
    thread = await db_session.get(ConversationThread, thread_id, populate_existing=True)
    assert thread.processing_status is ThreadProcessingStatus.PENDING


async def test_deleted_messages_invalidate_unsupported_knowledge(db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    first = await analyze_thread(db_session, thread_id, FakeGemini(site42_responder))

    # The confirming message is deleted at the source; only chatter-like content would remain.
    await upsert_messages(db_session, thread_id, [MessageIngest(
        external_message_id=m.external_id, author_external_id=m.author_id, content=m.content,
        sent_at=m.sent_at, deleted_at=datetime.now(UTC)) for m in SITE42.messages[1:]])
    await db_session.commit()
    second = await analyze_thread(db_session, thread_id, FakeGemini(IRRELEVANT))

    assert second.knowledge_item_id == first.knowledge_item_id
    item = await _item(db_session, thread_id)
    assert item.resolution_status is ResolutionStatus.UNKNOWN
    assert await _counts(db_session, thread_id) == (1, 1, 0)
    assert await db_session.scalar(select(func.count()).select_from(Message).where(
        Message.thread_id == thread_id)) == 4  # messages are kept, only marked deleted


async def test_demo_reset_is_scoped_to_synthetic_demo_data(db_session: AsyncSession, test_settings: Settings) -> None:
    await seed_demo_data(db_session, test_settings)
    other_thread = await _ingest_site42(db_session, upto=4)  # a non-demo source
    await analyze_thread(db_session, other_thread, FakeGemini(site42_responder))
    demo_lunch = await _thread_id(db_session, LUNCH.external_id)
    await analyze_thread(db_session, demo_lunch, FakeGemini(IRRELEVANT))

    summary = await reset_demo_data(db_session, test_settings)
    await db_session.commit()

    assert summary.threads == len(DEMO_THREADS) and summary.candidates == 1
    assert await _counts(db_session, other_thread) == (1, 1, 4)  # untouched
    assert await db_session.scalar(select(func.count()).select_from(ConversationThread).join(
        ConversationThread.source).where(CommunicationSource.external_source_id == DEMO_SOURCE_EXTERNAL_ID)) == 0


async def test_demo_reset_refuses_in_production(db_session: AsyncSession) -> None:
    with pytest.raises(PermissionError):
        await reset_demo_data(db_session, Settings(_env_file=None, environment="production"))


# ---- full simulated feed through the engine and API --------------------------------------

def demo_responder(contents: str):
    if "Site 42" in contents:
        return site42_responder(contents)
    return IRRELEVANT


def _engine_for(db_session: AsyncSession, gemini: FakeGemini) -> DiscoveryEngine:
    lock = asyncio.Lock()  # the test session is shared, so serialize its use

    @asynccontextmanager
    async def shared_session():
        async with lock:
            yield db_session

    return DiscoveryEngine(session_factory=shared_session, gemini_factory=lambda: gemini,
                           debounce_seconds=0.05, message_interval_seconds=0.0, max_concurrent_analyses=1)


async def _settle(engine: DiscoveryEngine) -> None:
    async with asyncio.timeout(10):
        while engine.simulation.running or engine.queued or engine.analyzing:
            await asyncio.sleep(0.02)


async def test_simulated_feed_discovers_knowledge_without_duplicates(
    api: httpx.AsyncClient, db_session: AsyncSession, test_settings: Settings
) -> None:
    await reset_demo_data(db_session, test_settings)
    await db_session.commit()
    gemini = FakeGemini(demo_responder)
    engine = _engine_for(db_session, gemini)
    app.dependency_overrides[get_discovery_engine] = lambda: engine

    assert (await api.post("/api/simulation/start")).json()["changed"] is True
    await _settle(engine)
    total = sum(len(t.messages) for t in DEMO_THREADS)
    assert engine.simulation.delivered == total

    threads = (await api.get("/api/discovery/threads?limit=100")).json()["items"]
    demo = {t["external_thread_id"]: t for t in threads if t["external_thread_id"].startswith("demo-thread")}
    site42 = demo["demo-thread-site42-connectivity"]["candidate"]
    assert site42["resolution_status"] == "confirmed_in_conversation"
    assert site42["approval_status"] == "unreviewed"
    assert demo["demo-thread-friday-lunch"]["candidate"]["detection_status"] == "rejected"

    detail = (await api.get(f"/api/knowledge/{site42['knowledge_item_id']}")).json()
    assert detail["discovery"]["classification"] == "confirmed_resolution"
    assert detail["discovery"]["model_confidence"] == 0.93
    assert "Router model" in detail["discovery"]["missing_information"]
    assert any(e["evidence_type"] == "confirmed_resolution" for e in detail["evidence"])

    status = (await api.get("/api/discovery/status")).json()
    metrics = status["metrics"]
    assert metrics["confirmed_resolutions"] >= 1 and metrics["messages_processed"] >= total

    # Restarting the feed delivers nothing new and creates no duplicates or Gemini calls.
    calls_before = len(gemini.calls)
    knowledge_before = (await api.get("/api/knowledge?limit=100")).json()["total"]
    assert (await api.post("/api/simulation/start")).json()["changed"] is True
    await _settle(engine)
    assert engine.simulation.delivered == 0 and engine.simulation.skipped_duplicates == total
    assert len(gemini.calls) == calls_before
    assert (await api.get("/api/knowledge?limit=100")).json()["total"] == knowledge_before

    events = (await api.get("/api/discovery/events")).json()
    assert any(e["kind"] == "analysis_skipped" for e in events)


async def test_analyze_endpoint_reports_gemini_unavailable(
    api: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    engine = _engine_for(db_session, FakeGemini(GeminiQuotaExceededError("Gemini rate limit or quota exceeded.")))
    app.dependency_overrides[get_discovery_engine] = lambda: engine

    response = await api.post(f"/api/threads/{thread_id}/analyze")
    assert response.status_code == 503
    assert "quota" in response.json()["detail"]
    assert (await api.post(f"/api/threads/{uuid.uuid4()}/analyze")).status_code == 404


async def test_analyze_endpoint_returns_result(api: httpx.AsyncClient, db_session: AsyncSession) -> None:
    thread_id = await _ingest_site42(db_session, upto=4)
    engine = _engine_for(db_session, FakeGemini(site42_responder))
    app.dependency_overrides[get_discovery_engine] = lambda: engine

    body = (await api.post(f"/api/threads/{thread_id}/analyze")).json()
    assert body["status"] == "analyzed" and body["resolution_status"] == "confirmed_in_conversation"
    again = (await api.post(f"/api/threads/{thread_id}/analyze")).json()
    assert again["status"] == "unchanged" and again["knowledge_item_id"] == body["knowledge_item_id"]



async def test_discovered_knowledge_is_embedded_automatically(
    db_session: AsyncSession, test_settings: Settings
) -> None:
    from app.models import KnowledgeChunk
    from tests.retrieval_fakes import FakeEmbedder

    await reset_demo_data(db_session, test_settings)
    await db_session.commit()
    embedder = FakeEmbedder()
    engine = _engine_for(db_session, FakeGemini(demo_responder))
    engine.debounce_seconds = 0.5  # well above the fake feed's delivery time (avoids timing flakes)
    engine.embedder_factory = lambda: embedder

    engine.start_simulation()
    await _settle(engine)

    item_id = await db_session.scalar(
        select(KnowledgeItem.id).join(KnowledgeItem.candidate).join(KnowledgeCandidate.thread)
        .where(ConversationThread.external_thread_id == SITE42.external_id))
    chunks = list(await db_session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_item_id == item_id)))
    assert len(chunks) == 1 and chunks[0].embedding is not None
    # Site 42 was analyzed twice (suggested -> confirmed); the chunk was rewritten, not duplicated.
    assert "confirmed in conversation" in chunks[0].content
    # Re-embedded after the update (at least the suggested and the confirmed version).
    assert len(embedder.document_calls) >= 2
    assert "confirmed in conversation" in embedder.document_calls[-1]
    assert any(e.kind == "indexed" for e in engine.events_after(0))


async def test_embedding_outage_does_not_block_discovery(
    db_session: AsyncSession, test_settings: Settings
) -> None:
    from app.models import KnowledgeChunk
    from tests.retrieval_fakes import FakeEmbedder

    await reset_demo_data(db_session, test_settings)
    await db_session.commit()
    engine = _engine_for(db_session, FakeGemini(demo_responder))
    engine.embedder_factory = lambda: FakeEmbedder(fail=True)

    engine.start_simulation()
    await _settle(engine)

    item_id = await db_session.scalar(
        select(KnowledgeItem.id).join(KnowledgeItem.candidate).join(KnowledgeCandidate.thread)
        .where(ConversationThread.external_thread_id == SITE42.external_id))
    assert item_id is not None  # knowledge saved anyway
    chunk = await db_session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_item_id == item_id))
    assert chunk is not None and chunk.embedding is None  # pending, retried by backfill
    assert any(e.kind == "index_pending" for e in engine.events_after(0))
