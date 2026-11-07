"""Email intake, entity binding with the inventory, access knowledge and time validity.

Isolated test database, scripted fake Gemini and fake embeddings (no API calls).
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.search import get_embedding_service
from app.core.config import Settings
from app.main import app
from app.models import (
    CommunicationSource,
    ConversationThread,
    KnowledgeCandidate,
    KnowledgeEntityLink,
    KnowledgeItem,
    Message,
)
from app.models.enums import KnowledgeType, SourceType
from app.seed.demo_data import DEMO_MAILBOX
from app.seed.demo_emails import load_demo_emails
from app.seed.inventory import ensure_inventory
from app.services.consolidation.service import ConsolidationConfig, consolidate_item
from app.services.discovery.analyzer import analyze_thread
from app.services.discovery.demo_reset import reset_demo_data
from app.services.email_ingest import import_emails, parse_json
from app.services.retrieval.indexing import index_item
from app.services.retrieval.search import SearchFilters, hybrid_search
from tests.consolidation_fakes import FakeConsolidationGemini, Rule
from tests.discovery_fakes import FakeGemini, act, analysis, ev
from tests.retrieval_fakes import FakeEmbedder

LOOSE = {"min_similarity": 0.05, "similarity_margin": 1.0}


@pytest.fixture(autouse=True)
def _no_background(monkeypatch: pytest.MonkeyPatch):
    """API routes schedule analysis on app.state.discovery; record instead of running."""
    calls: list = []

    class Recorder:
        def schedule_analysis(self, thread_id, title=None):
            calls.append(thread_id)

    previous = getattr(app.state, "discovery", None)
    app.state.discovery = Recorder()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
    yield calls
    app.state.discovery = previous
    app.dependency_overrides.pop(get_embedding_service, None)


# ---- email intake -----------------------------------------------------------------------------


async def test_email_reply_joins_its_thread_and_reimport_is_idempotent(db_session: AsyncSession) -> None:
    first = await import_emails(db_session, DEMO_MAILBOX, load_demo_emails())
    await db_session.commit()
    assert first.imported == 3 and first.duplicates == 0
    titles = sorted(title for _, title in first.threads)
    assert titles == ["Access to SITE-PELLO-03 (TRN-118)", "TRN-042 traffic not recovering after SFP replacement"]
    trn = next(t for t, title in first.threads if title.startswith("TRN-042"))
    messages = list(await db_session.scalars(select(Message).where(Message.thread_id == trn).order_by(Message.sent_at)))
    assert [m.author_external_id for m in messages] == ["veikko.vikkela@field-ops.elisa-echo.invalid",
                                                       "erkki.expert@network.elisa-echo.invalid"]
    assert "Should I replace the SFP again?" not in messages[1].content  # quoted history stripped

    again = await import_emails(db_session, DEMO_MAILBOX, load_demo_emails())
    assert again.imported == 0 and again.duplicates == 3 and again.threads == []
    source = await db_session.scalar(select(CommunicationSource).where(CommunicationSource.source_type == SourceType.EMAIL))
    assert source.external_source_id == f"mailbox:{DEMO_MAILBOX}"


async def test_subject_threading_and_disabled_mailbox(db_session: AsyncSession) -> None:
    mails = [parse_json({"from": "a@x.invalid", "subject": "Fan alarm on TRN-305", "body": "Fan alarm again.",
                         "date": "2026-10-01T08:00:00"}),
             parse_json({"from": "b@x.invalid", "subject": "RE: Fan alarm on TRN-305", "body": "Clean the filter.",
                         "date": "2026-10-01T09:00:00"})]
    result = await import_emails(db_session, "noc@x.invalid", mails)
    assert result.imported == 2 and len(result.threads) == 1  # no References: grouped by subject
    source = await db_session.get(CommunicationSource, result.source_id)
    source.enabled = False
    await db_session.commit()
    late = parse_json({"from": "c@x.invalid", "subject": "RE: Fan alarm on TRN-305", "body": "Done.",
                       "date": "2026-10-02T09:00:00"})
    skipped = await import_emails(db_session, "noc@x.invalid", [late])
    assert skipped.imported == 0 and skipped.skipped_reason


async def test_email_api_imports_and_schedules_analysis(api: httpx.AsyncClient, _no_background) -> None:
    r = await api.post("/api/integrations/email/import-samples")
    assert r.status_code == 200 and r.json()["imported"] == 3
    assert len(_no_background) == 2  # both email threads queued for discovery
    raw = ("From: Veikko <v@x.invalid>\nSubject: TRN-118 counters zero\nDate: Wed, 28 Oct 2026 07:00:00 +0000\n"
           "Message-ID: <q118@x.invalid>\n\nLink up, counters zero after SFP swap.")
    r = await api.post("/api/integrations/email/import", json={"mailbox": "field@x.invalid", "emails": [{"raw": raw}]})
    assert r.status_code == 200 and r.json()["imported"] == 1
    assert (await api.post("/api/integrations/email/import", json={"emails": [{"raw": "garbage"}]})).status_code == 422
    boxes = {b["mailbox"]: b for b in (await api.get("/api/integrations/email/mailboxes")).json()}
    assert boxes[DEMO_MAILBOX]["messages"] == 3 and boxes["field@x.invalid"]["threads"] == 1


async def test_email_import_is_development_only(api: httpx.AsyncClient) -> None:
    from app.core.config import get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="production")
    try:
        assert (await api.post("/api/integrations/email/import-samples")).status_code == 403
    finally:
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="test")


# ---- entity binding ---------------------------------------------------------------------------


async def trn042_thread(db: AsyncSession) -> ConversationThread:
    source = CommunicationSource(name="Teams test", source_type=SourceType.TEAMS, external_source_id="teams-test")
    thread = ConversationThread(source=source, external_thread_id="trn042", title="TRN-042 after SFP swap")
    texts = ["Changed the SFP on transmission node TRN-042. Link up, alarms cleared, no traffic.",
             "These older units: check counters; if zero, disable and enable the interface. Don't reboot.",
             "Did that. Traffic is back. These old units do this after an optical module replacement."]
    t0 = datetime(2026, 10, 5, 9, 14, tzinfo=UTC)
    db.add_all([thread, *[Message(thread=thread, external_message_id=f"m{i}", author_external_id=f"u{i}",
                                  content=t, sent_at=t0 + timedelta(minutes=i)) for i, t in enumerate(texts)]])
    await db.commit()
    return thread


def trn042_analysis(scope: str = "same_equipment_class"):
    return analysis(
        classification="confirmed_resolution", is_valuable_knowledge=True,
        title="Bounce the interface when traffic does not recover after SFP replacement",
        problem_description="Interface UP, optics normal, alarms cleared, but zero traffic after SFP replacement",
        equipment_identifiers=["TRN-042"], scope=scope, scope_description="older transmission units",
        trigger_events=["SFP replacement"],
        attempted_actions=[act("Disable and re-enable the interface", "successful", "M2", "M3")],
        resolution="Check traffic counters; if zero, disable and re-enable the interface before replacing hardware",
        resolution_status="confirmed_in_conversation",
        evidence=[ev("M1", "problem_report"), ev("M2", "suggested_solution"), ev("M3", "confirmed_resolution")])


async def links_of(db: AsyncSession, item_id) -> set[tuple[str, str, str, str]]:
    rows = await db.scalars(select(KnowledgeEntityLink).where(KnowledgeEntityLink.knowledge_item_id == item_id))
    return {(r.entity_type, r.label, r.relation, r.source) for r in rows}


async def test_knowledge_is_bound_to_node_class_site_and_event(db_session: AsyncSession) -> None:
    await ensure_inventory(db_session)
    thread = await trn042_thread(db_session)
    outcome = await analyze_thread(db_session, thread.id, FakeGemini(trn042_analysis()))
    links = await links_of(db_session, outcome.knowledge_item_id)
    assert ("equipment", "TRN-042", "observed_on", "conversation") in links
    assert ("unit_class", "TX-900 transmission unit (legacy generation)", "applies_to", "inventory") in links
    assert ("site", "SITE-OULU-07", "located_at", "inventory") in links
    assert ("event", "SFP replacement", "triggered_by", "conversation") in links
    item = await db_session.get(KnowledgeItem, outcome.knowledge_item_id)
    assert item.valid_from == datetime(2026, 10, 5, 9, 14, tzinfo=UTC) and item.valid_to is None

    # Re-analysis with device-only scope drops the class link (no duplicate rows either).
    outcome = await analyze_thread(db_session, thread.id, FakeGemini(trn042_analysis("this_equipment_only")), force=True)
    links = await links_of(db_session, outcome.knowledge_item_id)
    assert not any(t == "unit_class" for t, *_ in links) and ("equipment", "TRN-042", "observed_on", "conversation") in links


async def test_sibling_node_of_the_same_class_finds_the_knowledge(db_session: AsyncSession) -> None:
    await ensure_inventory(db_session)
    thread = await trn042_thread(db_session)
    outcome = await analyze_thread(db_session, thread.id, FakeGemini(trn042_analysis()))
    await index_item(db_session, outcome.knowledge_item_id, FakeEmbedder())

    sibling = await hybrid_search(db_session, "TRN-118 traffic not recovering", None, limit=5,
                                  filters=SearchFilters(), **LOOSE)
    hit = next(r for r in sibling.ranked if r.item_id == outcome.knowledge_item_id)
    assert hit.identifier is not None and "trn118 (same unit class)" in hit.matched_identifiers
    newer = await hybrid_search(db_session, "TRN-305 traffic not recovering", None, limit=5,
                                filters=SearchFilters(), **LOOSE)
    match = next((r for r in newer.ranked if r.item_id == outcome.knowledge_item_id), None)
    assert match is None or match.identifier is None  # different unit class: no identifier link


async def test_access_information_is_site_access_knowledge(db_session: AsyncSession) -> None:
    await ensure_inventory(db_session)
    result = await import_emails(db_session, DEMO_MAILBOX, [m for m in load_demo_emails() if "pello" in m.message_id])
    await db_session.commit()
    thread_id = result.threads[0][0]
    raw = analysis(classification="access_information", knowledge_type="site_access", is_valuable_knowledge=True,
                   title="Barrier key for SITE-PELLO-03", problem_description="Locked barrier on the private road",
                   resolution="Key is in the lockbox on the barrier post", resolution_status="suggested",
                   site_identifiers=["SITE-PELLO-03"], equipment_identifiers=["TRN-118"],
                   evidence=[ev("M1", "suggested_solution")])
    outcome = await analyze_thread(db_session, thread_id, FakeGemini(raw))
    await index_item(db_session, outcome.knowledge_item_id, FakeEmbedder())
    item = await db_session.get(KnowledgeItem, outcome.knowledge_item_id)
    assert item.knowledge_type is KnowledgeType.SITE_ACCESS
    assert ("site", "SITE-PELLO-03", "access_to", "conversation") in await links_of(db_session, item.id)
    found = await hybrid_search(db_session, "how to get through the barrier at SITE-PELLO-03", None, limit=5,
                                filters=SearchFilters(), **LOOSE)
    assert found.ranked and found.ranked[0].item_id == item.id


# ---- time validity ----------------------------------------------------------------------------


async def access_pair(db: AsyncSession):
    """Old lockbox email (2025) and the newer Teams note (2026) as two knowledge items."""
    from tests.integration.test_search import make_item

    old = await make_item(db, "old", title="OLD: Barrier key in the lockbox, code 4471",
                          problem="Locked barrier on the private road to SITE-PELLO-03",
                          resolution="Use the lockbox on the barrier post, code 4471",
                          messages=["Barrier key for SITE-PELLO-03 is in the lockbox, code 4471"])
    new = await make_item(db, "new", title="NEW: Barrier key now at the Pello depot",
                          problem="Locked barrier on the private road to SITE-PELLO-03, lockbox removed",
                          resolution="Pick up the key from the Pello depot key cabinet, tag P3",
                          messages=["The lockbox at the SITE-PELLO-03 barrier is gone",
                                    "Lock replaced, key now at the Pello depot, tag P3. Old lockbox info is no longer valid."])
    # make_item dates all messages 2026-10-01; move the old case to 2025.
    for m in await db.scalars(select(Message).join(KnowledgeCandidate, KnowledgeCandidate.thread_id == Message.thread_id)
                              .where(KnowledgeCandidate.id == old.candidate_id)):
        m.sent_at = m.sent_at - timedelta(days=570)
    old.valid_from = datetime(2025, 3, 12, tzinfo=UTC)
    new.valid_from = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    await db.commit()
    embedder = FakeEmbedder()
    for item in (old, new):
        await index_item(db, item.id, embedder)
    return old, new


async def test_newer_knowledge_makes_older_outdated_and_search_respects_time(db_session: AsyncSession) -> None:
    old, new = await access_pair(db_session)
    gemini = FakeConsolidationGemini({frozenset({"OLD", "NEW"}): Rule("same_problem", replaced="OLD")})
    await consolidate_item(db_session, new.id, gemini, ConsolidationConfig(min_similarity=0.05))
    await db_session.refresh(old)
    assert old.superseded_by_id == new.id and old.valid_to == datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    assert old.validity_note and new.valid_to is None

    query = "barrier key SITE-PELLO-03"
    now = {r.item_id for r in (await hybrid_search(db_session, query, None, limit=5, filters=SearchFilters(),
                                                   **LOOSE)).ranked}
    assert new.id in now and old.id not in now  # outdated advice is not served by default
    everything = {r.item_id for r in (await hybrid_search(
        db_session, query, None, limit=5, filters=SearchFilters(include_outdated=True), **LOOSE)).ranked}
    assert {old.id, new.id} <= everything
    in_2025 = {r.item_id for r in (await hybrid_search(
        db_session, query, None, limit=5, filters=SearchFilters(as_of=datetime(2025, 6, 1, tzinfo=UTC)),
        **LOOSE)).ranked}
    assert old.id in in_2025 and new.id not in in_2025  # what was believed true back then


async def test_api_shows_validity_and_replacement(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    old, new = await access_pair(db_session)
    gemini = FakeConsolidationGemini({frozenset({"OLD", "NEW"}): Rule("same_problem", replaced="OLD")})
    await consolidate_item(db_session, new.id, gemini, ConsolidationConfig(min_similarity=0.05))
    detail = (await api.get(f"/api/knowledge/{old.id}")).json()
    assert detail["valid_to"] and detail["superseded_by"]["id"] == str(new.id)
    body = (await api.post("/api/search", json={"query": "barrier key SITE-PELLO-03",
                                                "filters": {"include_outdated": True}})).json()
    by_id = {r["id"]: r for r in body["results"]}
    assert by_id[str(old.id)]["valid_to"] is not None and by_id[str(new.id)]["valid_to"] is None

    # A re-comparison that no longer sees a replacement reopens the old knowledge.
    gemini.rules[frozenset({"OLD", "NEW"})] = Rule("same_problem")
    await consolidate_item(db_session, new.id, gemini, ConsolidationConfig(min_similarity=0.05), force=True)
    await db_session.refresh(old)
    assert old.valid_to is None and old.superseded_by_id is None


async def test_demo_reset_covers_teams_and_email_demo_sources_only(db_session: AsyncSession,
                                                                   test_settings: Settings) -> None:
    await import_emails(db_session, DEMO_MAILBOX, load_demo_emails())
    other = await import_emails(db_session, "real-noc@x.invalid", [parse_json(
        {"from": "a@x.invalid", "subject": "Keep me", "body": "Real mailbox email.", "date": "2026-10-01T08:00:00"})])
    await db_session.commit()
    summary = await reset_demo_data(db_session, test_settings)
    await db_session.commit()
    assert summary.threads == 2  # the two demo email threads
    kept = await db_session.scalar(select(func.count()).select_from(ConversationThread).where(
        ConversationThread.communication_source_id == other.source_id))
    assert kept == 1


async def test_guide_prompt_knows_the_engineers_node_and_unit_class(db_session: AsyncSession) -> None:
    from app.ai.guide_schema import GuideDraft
    from app.services.guides.generator import generate_guide

    await ensure_inventory(db_session)
    thread = await trn042_thread(db_session)
    outcome = await analyze_thread(db_session, thread.id, FakeGemini(trn042_analysis()))
    await index_item(db_session, outcome.knowledge_item_id, FakeEmbedder())
    prompts: list[str] = []

    class GuideGemini:
        model = "fake-guide"
        configured = True

        async def generate_structured(self, *, system_instruction, contents, schema):
            prompts.append(contents)
            return GuideDraft(title="x", summary="x", sufficient_evidence=False, insufficiency_reason="stop",
                              nodes=[], edges=[], conflicts=[], uncertainties=[])

    await generate_guide(db_session, problem="TRN-118 traffic not recovering after SFP replacement",
                         equipment_identifier=None, embedder=FakeEmbedder(), gemini=GuideGemini(), **LOOSE)
    assert "<inventory>" in prompts[0] and '"node": "TRN-118"' in prompts[0]
    assert "TX-900 transmission unit (legacy generation)" in prompts[0]
    assert "unit_class: TX-900 transmission unit (legacy generation) (applies_to)" in prompts[0]
