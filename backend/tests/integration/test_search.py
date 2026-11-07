"""Phase 4 integration: indexing, vector/keyword/identifier retrieval and the search API.

Runs on the isolated test database with a deterministic fake embedder (no Gemini calls).
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.search import get_embedding_service
from app.core.config import Settings, get_settings
from app.main import app
from app.models import (
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
from app.models.enums import ApprovalStatus, EvidenceType, ResolutionStatus, SourceType
from app.services.retrieval.indexing import embed_pending_chunks, index_item
from app.services.retrieval.search import SearchFilters, hybrid_search
from tests.retrieval_fakes import FakeEmbedder

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
LOOSE = {"min_similarity": 0.05, "similarity_margin": 1.0}  # fake vectors are not calibrated


async def make_item(
    session: AsyncSession,
    key: str,
    *,
    title: str,
    problem: str,
    resolution: str,
    messages: list[str],
    equipment: list[str] = (),
    incidents: list[str] = (),
    status: ResolutionStatus = ResolutionStatus.CONFIRMED_IN_CONVERSATION,
    source_enabled: bool = True,
) -> KnowledgeItem:
    source = CommunicationSource(name=f"Search test {key}", source_type=SourceType.SIMULATED,
                                 external_source_id=f"search-{key}-{uuid.uuid4().hex[:6]}", enabled=source_enabled)
    thread = ConversationThread(source=source, external_thread_id=f"thr-{key}", title=title)
    msgs = [Message(thread=thread, external_message_id=f"{key}-{i}", author_external_id=f"u{i}",
                    author_display_name=f"Engineer {i} (synthetic)", content=text,
                    sent_at=T0 + timedelta(minutes=i)) for i, text in enumerate(messages)]
    candidate = KnowledgeCandidate(thread=thread, candidate_type="confirmed_resolution", title=title,
                                   extracted_data={"analysis": {"missing_information": ["Router model"]}})
    item = KnowledgeItem(
        candidate=candidate, title=title, problem_description=problem, resolution=resolution,
        resolution_status=status, symptoms=[problem],
        attempted_actions=[{"action": resolution, "outcome": "successful", "message_ids": []}],
        applicability_conditions=[],
    )
    item.evidence = [KnowledgeEvidence(message=msgs[0], evidence_type=EvidenceType.PROBLEM_REPORT),
                     KnowledgeEvidence(message=msgs[-1], evidence_type=EvidenceType.CONFIRMED_RESOLUTION)]
    item.equipment = [Equipment(equipment_identifier=e) for e in equipment]
    item.incidents = [Incident(incident_number=n, title=title) for n in incidents]
    session.add_all([*msgs, item])
    await session.commit()
    return item


async def site42(session: AsyncSession, **kw) -> KnowledgeItem:
    return await make_item(
        session, "site42", title="Restart DHCP relay service instead of rebooting router",
        problem="Intermittent connectivity, customer connections dropping every 20 minutes at Site 42",
        resolution="Restart the DHCP relay service on TEST-S42-RTR",
        messages=["Site 42 keeps dropping connections, rebooting the router did not help",
                  "Restart only the DHCP relay service", "That worked, connection stable"],
        equipment=["TEST-S42-RTR"], **kw)


async def bgp(session: AsyncSession, **kw) -> KnowledgeItem:
    return await make_item(
        session, "bgp", title="BGP session flapping due to MTU mismatch",
        problem="BGP neighbor session flapping with hold timer expired",
        resolution="Align MTU on the interconnect to 9000",
        messages=["BGP session on TEST-PE-03 flapping", "Aligned MTU, session stable"],
        equipment=["TEST-PE-03"], incidents=["INC-1042"], **kw)


async def chunks_of(session: AsyncSession, item_id: uuid.UUID) -> list[KnowledgeChunk]:
    session.expunge_all()
    return list(await session.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.knowledge_item_id == item_id).order_by(KnowledgeChunk.chunk_index)))


# ---- indexing ----------------------------------------------------------------------------

async def test_indexing_creates_one_embedded_chunk_and_skips_unchanged(db_session: AsyncSession) -> None:
    item = await site42(db_session)
    embedder = FakeEmbedder()

    first = await index_item(db_session, item.id, embedder)
    assert first.status == "indexed" and first.embedded == 1
    chunks = await chunks_of(db_session, item.id)
    assert len(chunks) == 1 and chunks[0].embedding is not None and len(chunks[0].embedding) == 768
    assert "Restart the DHCP relay service" in chunks[0].content
    assert "Engineer" not in chunks[0].content  # no personal conversation content

    second = await index_item(db_session, item.id, embedder)
    assert second.status == "unchanged" and len(embedder.document_calls) == 1  # no duplicate embedding
    assert len(await chunks_of(db_session, item.id)) == 1  # no duplicate rows


async def test_changed_knowledge_is_re_embedded_in_place(db_session: AsyncSession) -> None:
    item = await site42(db_session, status=ResolutionStatus.SUGGESTED)
    embedder = FakeEmbedder()
    await index_item(db_session, item.id, embedder)
    before = (await chunks_of(db_session, item.id))[0]
    before_id, before_content, before_embedding = before.id, before.content, list(before.embedding)

    loaded = await db_session.get(KnowledgeItem, item.id)
    loaded.resolution_status = ResolutionStatus.CONFIRMED_IN_CONVERSATION
    loaded.resolution = "Restart the DHCP relay service; confirmed stable afterwards"
    await db_session.commit()

    outcome = await index_item(db_session, item.id, embedder)
    after = await chunks_of(db_session, item.id)
    assert outcome.status == "indexed" and len(embedder.document_calls) == 2
    assert len(after) == 1 and after[0].id == before_id  # updated, not duplicated
    assert "confirmed in conversation" in after[0].content and after[0].content != before_content
    assert "suggested, not confirmed" in before_content
    assert list(after[0].embedding) != before_embedding


async def test_embedding_failure_keeps_knowledge_and_retries_later(db_session: AsyncSession) -> None:
    item = await site42(db_session)
    outcome = await index_item(db_session, item.id, FakeEmbedder(fail=True))
    assert outcome.status == "pending" and "unavailable" in outcome.error
    chunks = await chunks_of(db_session, item.id)
    assert len(chunks) == 1 and chunks[0].embedding is None  # text stored, embedding pending
    assert await db_session.get(KnowledgeItem, item.id) is not None  # knowledge preserved

    retry = await embed_pending_chunks(db_session, FakeEmbedder(), item_id=item.id)
    assert retry.embedded == 1 and retry.pending == 0


# ---- retrieval ---------------------------------------------------------------------------

async def _index_all(session: AsyncSession, *items: KnowledgeItem) -> FakeEmbedder:
    embedder = FakeEmbedder()
    for item in items:
        await index_item(session, item.id, embedder)
    return embedder


async def test_vector_retrieval_finds_differently_worded_problem(db_session: AsyncSession) -> None:
    a, b = await site42(db_session), await bgp(db_session)
    embedder = await _index_all(db_session, a, b)
    outcome = await hybrid_search(db_session, "customer connection dropping intermittently", embedder,
                                  limit=5, filters=SearchFilters(), **LOOSE)
    assert outcome.semantic_status == "used"
    assert outcome.ranked[0].item_id == a.id and outcome.ranked[0].semantic is not None
    assert 0 < outcome.ranked[0].semantic.score <= 1  # real cosine similarity


async def test_keyword_retrieval_works_without_embeddings(db_session: AsyncSession) -> None:
    a, b = await site42(db_session), await bgp(db_session)
    await _index_all(db_session, a, b)
    outcome = await hybrid_search(db_session, "hold timer expired", FakeEmbedder(configured=False),
                                  limit=5, filters=SearchFilters(), **LOOSE)
    assert outcome.semantic_status == "not_configured"
    assert outcome.ranked[0].item_id == b.id and outcome.ranked[0].keyword is not None


async def test_embedding_api_failure_falls_back_to_keyword(db_session: AsyncSession) -> None:
    a, b = await site42(db_session), await bgp(db_session)
    await _index_all(db_session, a, b)
    outcome = await hybrid_search(db_session, "DHCP relay service", FakeEmbedder(fail=True),
                                  limit=5, filters=SearchFilters(), **LOOSE)
    assert outcome.semantic_status == "unavailable" and "unavailable" in outcome.semantic_detail
    assert outcome.ranked and outcome.ranked[0].item_id == a.id
    assert all(r.semantic is None for r in outcome.ranked)  # no fake semantic signal


async def test_exact_identifiers_are_prioritized(db_session: AsyncSession) -> None:
    a, b = await site42(db_session), await bgp(db_session)
    embedder = await _index_all(db_session, a, b)
    # Wording points at the DHCP item, but the incident number belongs to the BGP item.
    outcome = await hybrid_search(db_session, "connection dropping, see INC-1042", embedder,
                                  limit=5, filters=SearchFilters(), **LOOSE)
    assert outcome.identifiers == ["inc1042"]
    assert outcome.ranked[0].item_id == b.id and outcome.ranked[0].matched_identifiers == ["inc1042"]

    by_equipment = await hybrid_search(db_session, "test-s42-rtr", embedder, limit=5,
                                       filters=SearchFilters(), **LOOSE)
    assert by_equipment.ranked[0].item_id == a.id


async def test_search_with_no_results_and_empty_index(db_session: AsyncSession) -> None:
    empty = await hybrid_search(db_session, "router dropping", FakeEmbedder(), limit=5, filters=SearchFilters())
    assert empty.semantic_status == "no_embeddings" and empty.ranked == []

    a = await site42(db_session)
    embedder = await _index_all(db_session, a)
    nothing = await hybrid_search(db_session, "printer toner cartridge", embedder, limit=5,
                                  filters=SearchFilters(), min_similarity=0.5)
    assert nothing.ranked == []


async def test_filters_and_disabled_sources_are_applied_in_retrieval(db_session: AsyncSession) -> None:
    a, b = await site42(db_session), await bgp(db_session)
    hidden = await make_item(db_session, "hidden", title="Restart DHCP relay hidden source",
                             problem="connection dropping", resolution="Restart DHCP relay service",
                             messages=["x", "y"], source_enabled=False)
    embedder = await _index_all(db_session, a, b, hidden)

    everything = await hybrid_search(db_session, "DHCP relay connection dropping", embedder, limit=10,
                                     filters=SearchFilters(), **LOOSE)
    assert hidden.id not in {r.item_id for r in everything.ranked}  # unauthorized source excluded

    approved_only = await hybrid_search(db_session, "DHCP relay connection dropping", embedder, limit=10,
                                        filters=SearchFilters(approval_status=ApprovalStatus.APPROVED), **LOOSE)
    assert approved_only.ranked == []
    by_equipment = await hybrid_search(db_session, "session flapping connection", embedder, limit=10,
                                       filters=SearchFilters(equipment_identifier="test-pe-03"), **LOOSE)
    assert [r.item_id for r in by_equipment.ranked] == [b.id]


# ---- API ---------------------------------------------------------------------------------

async def test_search_api_returns_evidence_backed_results(api: httpx.AsyncClient, db_session: AsyncSession) -> None:
    a, b = await site42(db_session), await bgp(db_session)
    embedder = await _index_all(db_session, a, b)
    # Delete one supporting message at the source: its text must no longer be shown.
    deleted = await db_session.scalar(select(Message).where(Message.external_message_id == "bgp-0"))
    deleted.deleted_at = T0 + timedelta(days=1)
    await db_session.commit()

    app.dependency_overrides[get_embedding_service] = lambda: embedder
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="test", search_min_similarity=0.05, search_similarity_margin=1.0)

    body = {"query": "connections keep dropping even after rebooting the router", "limit": 5}
    response = await api.post("/api/search", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["retrieval"]["semantic"] == "used"
    top = data["results"][0]
    assert top["id"] == str(a.id)
    assert top["resolution_status"] == "confirmed_in_conversation" and top["approval_status"] == "unreviewed"
    assert top["evidence_status"] == "supported" and top["missing_information"] == ["Router model"]
    assert top["equipment_identifiers"] == ["TEST-S42-RTR"]
    evidence = top["evidence"]
    assert [e["evidence_type"] for e in evidence] == ["problem_report", "confirmed_resolution"]
    assert evidence[1]["excerpt"] == "That worked, connection stable"
    assert evidence[1]["author"] == "Engineer 2 (synthetic)" and evidence[1]["source_name"].startswith("Search test")
    assert "semantic" in top["ranking"]["matched_by"] and top["ranking"]["semantic_similarity"] > 0

    # Repeating the search returns the same ranking and reuses the query embedding.
    again = (await api.post("/api/search", json=body)).json()
    assert [r["id"] for r in again["results"]] == [r["id"] for r in data["results"]]

    bgp_result = (await api.post("/api/search", json={"query": "INC-1042"})).json()["results"][0]
    assert bgp_result["id"] == str(b.id)
    gone = next(e for e in bgp_result["evidence"] if e["deleted_at_source"])
    assert gone["excerpt"] is None


async def test_search_api_reports_missing_evidence(api: httpx.AsyncClient, db_session: AsyncSession) -> None:
    item = await site42(db_session)
    loaded = await db_session.get(KnowledgeItem, item.id)
    await db_session.refresh(loaded, ["evidence"])
    loaded.evidence = []
    await db_session.commit()
    await _index_all(db_session, item)
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder(configured=False)

    result = (await api.post("/api/search", json={"query": "DHCP relay service"})).json()
    assert result["retrieval"]["semantic"] == "not_configured"
    assert result["results"][0]["evidence_status"] == "missing" and result["results"][0]["evidence"] == []


async def test_chunk_count_stays_one_per_item(db_session: AsyncSession) -> None:
    a = await site42(db_session)
    embedder = FakeEmbedder()
    for _ in range(3):
        await index_item(db_session, a.id, embedder)
    count = await db_session.scalar(select(func.count()).select_from(KnowledgeChunk)
                                    .where(KnowledgeChunk.knowledge_item_id == a.id))
    assert count == 1
