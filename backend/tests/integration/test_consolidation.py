"""Phase 6B integration: candidate retrieval, validated relationships, grouping rules,
summaries, retries, access filtering and the read APIs.

Runs on the isolated test database with fake embeddings and a scripted fake Gemini.
"""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import GeminiUnavailableError
from app.api.routes.search import get_embedding_service
from app.main import app
from app.models import (
    CommunicationSource,
    ConversationThread,
    Equipment,
    KnowledgeCandidate,
    KnowledgeConsolidationState,
    KnowledgeGroup,
    KnowledgeGroupMember,
    KnowledgeItem,
    KnowledgeRelationship,
)
from app.models.enums import ResolutionStatus
from app.services.consolidation.candidates import find_candidates
from app.services.consolidation.service import (
    ConsolidationConfig,
    consolidate_item,
    items_needing_consolidation,
    remove_ineligible_memberships,
)
from app.services.retrieval.indexing import index_item
from tests.consolidation_fakes import FakeConsolidationGemini, Rule
from tests.integration.test_search import make_item
from tests.retrieval_fakes import FakeEmbedder

CONFIG = ConsolidationConfig(candidate_limit=6, min_similarity=0.05, max_group_size=12)


async def s42(session: AsyncSession) -> KnowledgeItem:
    return await make_item(
        session, "s42", title="S42: Restart the DHCP relay service instead of rebooting",
        problem="Customers behind the Site 42 router lose sessions every 20-30 minutes",
        resolution="Restart only the DHCP relay service",
        messages=["Site 42 customers lose sessions every 20-30 minutes, router reboot did not help",
                  "Restart only the DHCP relay service", "That worked, connection stable now"])


async def s58(session: AsyncSession) -> KnowledgeItem:
    return await make_item(
        session, "s58", title="S58: DHCP relay restart stops session drops",
        problem="Site 58 router on firmware 3.2: customers keep losing sessions every 20 minutes",
        resolution="Restart the DHCP relay service",
        messages=["Customers lose sessions every 20 minutes at Site 58, router on firmware 3.2",
                  "Restarted the DHCP relay service, no drops for an hour"])


async def s17(session: AsyncSession) -> KnowledgeItem:
    return await make_item(
        session, "s17", title="S17: Fix DHCP lease time after relay restart failed",
        problem="Site 17 router on firmware 4.0: customers lose sessions every half hour",
        resolution="Set the DHCP lease time back to 24 hours",
        messages=["Site 17 customers lose sessions every half hour, firmware 4.0. Restarted the DHCP relay, no help",
                  "Lease time was 60 seconds, set to 24 hours, drops stopped"])


async def bgp(session: AsyncSession) -> KnowledgeItem:
    return await make_item(
        session, "bgp", title="BGP: Align MTU on PE-03 interconnect",
        problem="BGP session flapping, hold timer expired", resolution="Align MTU to 9000",
        messages=["BGP session keeps flapping with hold timer expired", "Aligned MTU to 9000, stable"])


FIRMWARE = {"firmware": {"S58": "3.2", "S17": "4.0", "S42": None}}
RULES = {
    frozenset({"S42", "S58"}): Rule("supporting_evidence", unknown=["firmware of Site 42"]),
    frozenset({"S58", "S17"}): Rule("different_outcome", outcome="different_outcome", conditions=FIRMWARE),
    frozenset({"S42", "S17"}): Rule("different_outcome", outcome="different_outcome", conditions=FIRMWARE),
}


async def indexed(session: AsyncSession, *items: KnowledgeItem) -> None:
    embedder = FakeEmbedder()
    for item in items:
        await index_item(session, item.id, embedder)


async def group_of(session: AsyncSession, item: KnowledgeItem):
    return await session.scalar(select(KnowledgeGroupMember.group_id)
                                .where(KnowledgeGroupMember.knowledge_item_id == item.id))


async def relationship(session: AsyncSession, a: KnowledgeItem, b: KnowledgeItem) -> KnowledgeRelationship:
    lo, hi = sorted([a.id, b.id])
    return await session.scalar(select(KnowledgeRelationship).where(
        KnowledgeRelationship.source_knowledge_id == lo, KnowledgeRelationship.target_knowledge_id == hi))


async def demo_cases(session: AsyncSession, gemini: FakeConsolidationGemini):
    a, b, c, d = await s42(session), await s58(session), await s17(session), await bgp(session)
    await indexed(session, a, b, c, d)
    for item in (a, b, c, d):
        await consolidate_item(session, item.id, gemini, CONFIG)
    return a, b, c, d


# ---- candidates ---------------------------------------------------------------------------


async def test_candidates_are_bounded_exclude_self_and_need_embeddings(db_session: AsyncSession) -> None:
    a, b, c, d = await s42(db_session), await s58(db_session), await s17(db_session), await bgp(db_session)
    assert await find_candidates(db_session, a.id, limit=5, min_similarity=0.05) == []  # nothing embedded
    await indexed(db_session, a, b, c, d)
    found = await find_candidates(db_session, a.id, limit=2, min_similarity=0.05)
    assert len(found) == 2 and a.id not in {f.knowledge_id for f in found}
    assert d.id not in {f.knowledge_id for f in found}  # the closest ones are the Site cases
    strict = await find_candidates(db_session, a.id, limit=5, min_similarity=0.99)
    assert strict == []


# ---- grouping, relationships, summaries ---------------------------------------------------


async def test_supporting_and_conflicting_cases_form_one_group(db_session: AsyncSession) -> None:
    gemini = FakeConsolidationGemini(RULES)
    a, b, c, d = await demo_cases(db_session, gemini)

    group_id = await group_of(db_session, a)
    assert group_id is not None and await group_of(db_session, b) == group_id == await group_of(db_session, c)
    assert await group_of(db_session, d) is None  # unrelated BGP case

    support = await relationship(db_session, a, b)
    assert support.relationship_type == "supporting_evidence" and support.source_evidence_ids
    assert support.unknown_conditions == ["firmware of Site 42"]
    conflict = await relationship(db_session, b, c)
    assert conflict.relationship_type == "different_outcome"
    values = {conflict.conditions[0]["source_value"], conflict.conditions[0]["target_value"]}
    assert values == {"3.2", "4.0"}
    # Site 42 never states a firmware: it stays unknown, never assumed equal.
    a_c = (await relationship(db_session, a, c)).conditions[0]
    assert None in (a_c["source_value"], a_c["target_value"])

    group = await db_session.get(KnowledgeGroup, group_id)
    await db_session.refresh(group)
    data = group.summary_data
    assert data["independent_conversations"] == 3 and data["case_count"] == 3
    assert data["review_status"] == "unreviewed" and data["conflict_count"] == 2
    assert data["known_environment"] == ["firmware 3.2", "firmware 4.0"]  # invented 9.9 removed
    assert [s["description"] for s in data["solutions"]] == ["Restart the DHCP relay service"]
    assert len(data["solutions"][0]["knowledge_ids"]) == 3


async def test_same_symptoms_with_unrelated_cause_stay_ungrouped(db_session: AsyncSession) -> None:
    gemini = FakeConsolidationGemini({frozenset({"S42", "S17"}): Rule("related_symptoms", outcome="not_comparable")})
    a, c = await s42(db_session), await s17(db_session)
    await indexed(db_session, a, c)
    await consolidate_item(db_session, a.id, gemini, CONFIG)
    outcome = await consolidate_item(db_session, c.id, gemini, CONFIG)
    assert outcome.status == "done" and outcome.related == 1 and outcome.group_id is None
    assert (await relationship(db_session, a, c)).relationship_type == "related_symptoms"
    assert await db_session.scalar(select(func.count()).select_from(KnowledgeGroup)) == 0


async def test_no_transitive_grouping(db_session: AsyncSession) -> None:
    # S42~S58 and S58~S17 are strong, but S42 and S17 are unrelated: S17 must not join.
    rules = {frozenset({"S42", "S58"}): Rule("same_problem"), frozenset({"S58", "S17"}): Rule("same_problem")}
    gemini = FakeConsolidationGemini(rules)
    a, b, c = await s42(db_session), await s58(db_session), await s17(db_session)
    await indexed(db_session, a, b, c)
    await consolidate_item(db_session, a.id, gemini, CONFIG)
    await consolidate_item(db_session, b.id, gemini, CONFIG)
    outcome = await consolidate_item(db_session, c.id, gemini, CONFIG)
    assert await group_of(db_session, a) == await group_of(db_session, b) is not None
    assert outcome.group_action == "ambiguous" and await group_of(db_session, c) is None
    assert (await relationship(db_session, b, c)).relationship_type == "same_problem"  # still visible


async def test_invalid_evidence_ids_never_group(db_session: AsyncSession) -> None:
    rules = {frozenset({"S42", "S58"}): Rule("same_problem", first_refs=["B1"], second_refs=["A7"])}
    gemini = FakeConsolidationGemini(rules)
    a, b = await s42(db_session), await s58(db_session)
    await indexed(db_session, a, b)
    await consolidate_item(db_session, a.id, gemini, CONFIG)
    await consolidate_item(db_session, b.id, gemini, CONFIG)
    row = await relationship(db_session, a, b)
    assert row.relationship_type == "related_symptoms" and row.source_evidence_ids == row.target_evidence_ids == []
    assert any("Ignored evidence" in n for n in row.validation_notes)
    assert await group_of(db_session, a) is None


async def test_duplicate_conversations_are_one_relationship_and_reruns_are_idempotent(db_session: AsyncSession) -> None:
    gemini = FakeConsolidationGemini({frozenset({"S42", "S58"}): Rule("same_problem")})
    a, b = await s42(db_session), await s58(db_session)
    await indexed(db_session, a, b)
    await consolidate_item(db_session, a.id, gemini, CONFIG)
    first = await consolidate_item(db_session, b.id, gemini, CONFIG)
    assert first.status == "done" and first.reused == 1 and first.compared == 0  # pair already compared
    calls = len(gemini.pair_calls)

    again = await consolidate_item(db_session, b.id, gemini, CONFIG)
    assert again.status == "unchanged" and len(gemini.pair_calls) == calls
    assert await db_session.scalar(select(func.count()).select_from(KnowledgeRelationship)) == 1
    assert await db_session.scalar(select(func.count()).select_from(KnowledgeGroupMember)) == 2

    forced = await consolidate_item(db_session, b.id, gemini, CONFIG, force=True)
    assert forced.compared == 1 and await db_session.scalar(
        select(func.count()).select_from(KnowledgeRelationship)) == 1


async def test_reanalysis_recompares_changed_knowledge(db_session: AsyncSession) -> None:
    gemini = FakeConsolidationGemini({frozenset({"S42", "S58"}): Rule("same_problem")})
    a, b = await s42(db_session), await s58(db_session)
    await indexed(db_session, a, b)
    await consolidate_item(db_session, a.id, gemini, CONFIG)
    assert await group_of(db_session, a) is not None

    # The conversation continued: the extracted knowledge changed and now conflicts.
    gemini.rules[frozenset({"S42", "S58"})] = Rule("unrelated", outcome="not_comparable")
    a.resolution = "Replace the router power supply"
    a.resolution_status = ResolutionStatus.SUGGESTED
    await db_session.commit()
    await indexed(db_session, a)
    outcome = await consolidate_item(db_session, a.id, gemini, CONFIG)
    assert outcome.compared == 1 and outcome.group_action is not None
    assert (await relationship(db_session, a, b)).relationship_type == "unrelated"
    assert await group_of(db_session, a) is None and await group_of(db_session, b) is None
    assert await db_session.scalar(select(func.count()).select_from(KnowledgeGroup)) == 0  # group of one removed


async def test_missing_embedding_uses_identifiers_and_retries_later(db_session: AsyncSession) -> None:
    gemini = FakeConsolidationGemini({frozenset({"S42", "S58"}): Rule("same_problem", equipment=["TEST-RTR-SHARED"])})
    a, b = await s42(db_session), await s58(db_session)
    shared = Equipment(equipment_identifier="TEST-RTR-SHARED")
    a.equipment.append(shared)
    b.equipment.append(shared)
    await db_session.commit()

    outcome = await consolidate_item(db_session, a.id, gemini, CONFIG)  # nothing embedded yet
    assert outcome.status == "retry" and "Embedding pending" in outcome.error
    assert outcome.compared == 1  # shared identifier still nominated the pair
    assert a.id in await items_needing_consolidation(db_session)

    await indexed(db_session, a, b)
    assert (await consolidate_item(db_session, a.id, gemini, CONFIG)).status == "done"


async def test_gemini_failure_keeps_knowledge_and_marks_retry(db_session: AsyncSession) -> None:
    gemini = FakeConsolidationGemini({frozenset({"S42", "S58"}): Rule("same_problem")})
    a, b = await s42(db_session), await s58(db_session)
    await indexed(db_session, a, b)
    gemini.fail = GeminiUnavailableError("Gemini is temporarily unavailable (HTTP 503).")

    outcome = await consolidate_item(db_session, a.id, gemini, CONFIG)
    assert outcome.status == "retry" and "503" in outcome.error
    assert await db_session.get(KnowledgeItem, a.id) is not None
    state = await db_session.get(KnowledgeConsolidationState, a.id)
    assert state.status == "retry"
    assert set(await items_needing_consolidation(db_session)) >= {a.id, b.id}

    gemini.fail = None
    assert (await consolidate_item(db_session, a.id, gemini, CONFIG)).status == "done"
    assert await group_of(db_session, a) is not None


async def test_disabled_sources_are_excluded_everywhere(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    gemini = FakeConsolidationGemini(RULES)
    a, b, c, _ = await demo_cases(db_session, gemini)
    group_id = await group_of(db_session, a)

    source = await db_session.scalar(
        select(CommunicationSource).join(ConversationThread).join(KnowledgeCandidate)
        .where(KnowledgeCandidate.id == b.candidate_id))
    source.enabled = False
    await db_session.commit()

    assert b.id not in {f.knowledge_id for f in await find_candidates(db_session, a.id, limit=5, min_similarity=0.05)}
    related = (await api.get(f"/api/knowledge/{a.id}/related")).json()
    assert b.id.hex not in str(related).replace("-", "")
    assert (await api.get(f"/api/knowledge/{b.id}/related")).status_code == 404
    detail = (await api.get(f"/api/knowledge-groups/{group_id}")).json()
    assert {m["id"] for m in detail["members"]} == {str(a.id), str(c.id)} and detail["case_count"] == 2
    rels = (await api.get(f"/api/knowledge-groups/{group_id}/relationships")).json()
    assert all(str(b.id) not in (r["source"]["id"], r["target"]["id"]) for r in rels)

    assert await remove_ineligible_memberships(db_session) == 1
    assert (await consolidate_item(db_session, b.id, gemini, CONFIG)).status == "skipped"


# ---- APIs -----------------------------------------------------------------------------------


async def test_related_and_group_endpoints(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    gemini = FakeConsolidationGemini(RULES)
    a, b, c, d = await demo_cases(db_session, gemini)

    related = (await api.get(f"/api/knowledge/{b.id}/related")).json()
    assert related["group"]["case_count"] == 3 and related["group"]["independent_conversations"] == 3
    types = [r["relationship_type"] for r in related["relationships"]]
    assert types == ["supporting_evidence", "different_outcome"]  # strongest first, unrelated omitted
    evidence = related["relationships"][0]
    assert evidence["source_evidence"] and evidence["source_evidence"][0]["excerpt"]

    groups = (await api.get("/api/knowledge-groups")).json()
    assert groups["total"] == 1 and groups["items"][0]["review_status"] == "unreviewed"
    group_id = groups["items"][0]["id"]
    detail = (await api.get(f"/api/knowledge-groups/{group_id}")).json()
    assert len(detail["members"]) == 3 and detail["solutions"][0]["outcome"] == "mixed"
    assert detail["missing_information"] == ["Firmware version for Site 42"] and not detail["summary_pending"]
    rels = (await api.get(f"/api/knowledge-groups/{group_id}/relationships")).json()
    assert len(rels) == 3

    assert (await api.get(f"/api/knowledge/{d.id}/related")).json()["relationships"] == []
    assert (await api.get("/api/knowledge-groups/00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_search_exposes_related_groups(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    gemini = FakeConsolidationGemini(RULES)
    await demo_cases(db_session, gemini)
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
    try:
        body = (await api.post("/api/search", json={"query": "customers lose sessions DHCP relay", "limit": 5})).json()
    finally:
        app.dependency_overrides.pop(get_embedding_service, None)
    grouped = [r for r in body["results"] if r["group_id"]]
    assert len(grouped) >= 2  # individual results are still listed
    assert len(body["related_groups"]) == 1 and body["related_groups"][0]["case_count"] == 3


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_embedding_service, None)


async def test_guide_generation_uses_consolidated_knowledge(db_session: AsyncSession) -> None:
    from app.ai.guide_schema import GuideDraft
    from app.services.guides.generator import generate_guide

    a, b, c, _ = await demo_cases(db_session, FakeConsolidationGemini(RULES))
    prompts: list[str] = []

    class GuideGemini:
        model = "fake-guide"
        configured = True

        async def generate_structured(self, *, system_instruction, contents, schema):
            assert schema is GuideDraft
            prompts.append(contents)
            return GuideDraft(title="x", summary="x", sufficient_evidence=False,
                              insufficiency_reason="test stops here", nodes=[], edges=[], conflicts=[],
                              uncertainties=[])

    await generate_guide(db_session, problem="Site 42 customers lose sessions, DHCP relay",
                         equipment_identifier=None, embedder=FakeEmbedder(), gemini=GuideGemini(),
                         min_similarity=0.05, similarity_margin=1.0)
    prompt = prompts[0]
    assert "<related_cases>" in prompt and "different_outcome" in prompt
    # All three group members are in the context, so the guide can branch on firmware.
    for item in (a, b, c):
        assert item.title in prompt
    assert '"firmware"' in prompt and "4.0" in prompt and "unknown" in prompt
