"""Phase 6C integration: troubleshooting feedback as new evidence.

Isolated test database, fake embeddings and scripted fake Gemini (no API calls). The API's
background group refresh is replaced by a recorder, so tests never reach another database.
"""

import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import GeminiUnavailableError
from app.api.routes.search import get_embedding_service
from app.main import app
from app.models import GuideNode, KnowledgeItem, TroubleshootingFeedback
from app.models.enums import ApprovalStatus, ResolutionStatus
from app.services.consolidation.service import ConsolidationConfig, consolidate_item, refresh_group_for_item
from app.services.feedback.summary import MIN_SAMPLE_FOR_RATE, feedback_summary
from tests.consolidation_fakes import FakeConsolidationGemini, Rule
from tests.integration.test_guides import ScriptedGemini, expert_draft_from, generate, two_experts
from tests.retrieval_fakes import FakeEmbedder


class RefreshRecorder:
    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []

    def schedule_feedback_refresh(self, item_id: uuid.UUID) -> None:
        self.calls.append(item_id)


@pytest.fixture(autouse=True)
def recorder():
    previous = getattr(app.state, "discovery", None)
    rec = RefreshRecorder()
    app.state.discovery = rec
    yield rec
    app.state.discovery = previous


@pytest.fixture(autouse=True)
def _fake_embedder():
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
    yield
    app.dependency_overrides.pop(get_embedding_service, None)


async def setup(db: AsyncSession):
    """Two knowledge items, a guide from them, and a node map by key."""
    a, b, embedder = await two_experts(db)
    guide = await generate(db, embedder, ScriptedGemini(expert_draft_from))
    nodes = {n.node_key: n for n in await db.scalars(select(GuideNode).where(GuideNode.guide_id == guide.id))}
    return a, b, guide, nodes


async def session_at_recommendation(api: httpx.AsyncClient, guide_id) -> str:
    """Start a session and answer until the 'Restart the DHCP relay service' step (n3)."""
    body = (await api.post("/api/troubleshooting/sessions", json={"guide_id": str(guide_id)})).json()
    sid = body["id"]
    for label in ("Continue", "No"):
        r = await api.post(f"/api/troubleshooting/sessions/{sid}/steps", json={"type": "answer", "answer_label": label})
        assert r.status_code == 200, r.text
    return sid


def payload(sid: str, node: GuideNode, item: KnowledgeItem, **kw) -> dict:
    base = {"troubleshooting_session_id": sid, "guide_node_id": str(node.id), "knowledge_item_id": str(item.id),
            "attempted": True, "outcome": "resolved"}
    base.update(kw)
    return base


async def post(api: httpx.AsyncClient, body: dict, token: str | None = None) -> httpx.Response:
    headers = {"X-Feedback-Token": token} if token else {}
    return await api.post("/api/troubleshooting/feedback", json=body, headers=headers)


# ---- submission and validation ------------------------------------------------------------


async def test_successful_feedback_is_saved_as_self_reported_evidence(
    db_session: AsyncSession, api: httpx.AsyncClient, recorder: RefreshRecorder
) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    r = await post(api, payload(sid, nodes["n3"], a, firmware_version="3.2", equipment_identifier="Site 42",
                                engineer_notes="Restarted the relay; stable for an hour.",
                                environment_details={"router family": "edge"}))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] and body["edit_token"] and body["origin"] == "troubleshooting_feedback"
    assert body["verification_status"] == "self_reported" and body["relation_to_original"] == "supports"
    assert body["recommendation"] == "Restart the DHCP relay service" and body["firmware_version"] == "3.2"
    assert recorder.calls == [a.id]  # group summary refresh scheduled in the background


async def test_failed_and_partial_outcomes(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    failed = (await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a,
                                      outcome="not_resolved", firmware_version="4.0"))).json()
    assert failed["outcome"] == "not_resolved" and failed["relation_to_original"] == "contradicts"
    partial = (await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a,
                                       outcome="partially_resolved"))).json()
    assert partial["relation_to_original"] == "mixed"


async def test_not_attempted_records_no_outcome(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    body = payload(sid, nodes["n3"], a, attempted=False)
    body.pop("outcome")
    saved = (await post(api, body)).json()
    assert saved["attempted"] is False and saved["outcome"] == "not_attempted"
    summary = await feedback_summary(db_session, a.id)
    assert summary.attempts == 0 and summary.counts.not_attempted == 1 and summary.counts.resolved == 0


async def test_inconsistent_combinations_and_client_verification_are_rejected(
    db_session: AsyncSession, api: httpx.AsyncClient
) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    assert (await post(api, payload(sid, nodes["n3"], a, attempted=False, outcome="resolved"))).status_code == 422
    no_outcome = payload(sid, nodes["n3"], a)
    no_outcome.pop("outcome")
    assert (await post(api, no_outcome)).status_code == 422
    assert (await post(api, payload(sid, nodes["n3"], a, outcome="not_attempted"))).status_code == 422
    forged = payload(sid, nodes["n3"], a, verification_status="independently_verified")
    assert (await post(api, forged)).status_code == 422
    assert await db_session.scalar(select(func.count()).select_from(TroubleshootingFeedback)) == 0


async def test_duplicate_submissions_create_one_record(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    body = payload(sid, nodes["n3"], a, firmware_version="3.2")
    first, second = await post(api, body), await post(api, body)
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["created"] is False and second.json()["edit_token"] is None
    assert second.json()["id"] == first.json()["id"]
    # Different feedback for the same recommendation without the token is not a new report.
    assert (await post(api, {**body, "outcome": "not_resolved"})).status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(TroubleshootingFeedback)) == 1


async def test_feedback_correction_keeps_history_and_recalculates(
    db_session: AsyncSession, api: httpx.AsyncClient
) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    created = (await post(api, payload(sid, nodes["n3"], a))).json()
    token = created["edit_token"]
    r = await api.patch(f"/api/troubleshooting/feedback/{created['id']}", headers={"X-Feedback-Token": token},
                        json={"attempted": True, "outcome": "not_resolved", "firmware_version": "4.0"})
    assert r.status_code == 200 and r.json()["outcome"] == "not_resolved" and r.json()["revision"] == 2
    row = await db_session.get(TroubleshootingFeedback, uuid.UUID(created["id"]))
    await db_session.refresh(row)
    assert row.revisions[0]["outcome"] == "resolved" and row.revisions[0]["revision"] == 1
    summary = (await api.get(f"/api/knowledge/{a.id}/feedback/summary")).json()
    assert summary["counts"]["resolved"] == 0 and summary["counts"]["not_resolved"] == 1
    # POST with the token is also accepted as a correction.
    again = await post(api, payload(sid, nodes["n3"], a, outcome="partially_resolved"), token=token)
    assert again.status_code == 200 and again.json()["revision"] == 3


async def test_unauthorized_modification_is_rejected(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    created = (await post(api, payload(sid, nodes["n3"], a))).json()
    change = {"attempted": True, "outcome": "not_resolved"}
    url = f"/api/troubleshooting/feedback/{created['id']}"
    assert (await api.patch(url, json=change)).status_code == 403
    assert (await api.patch(url, json=change, headers={"X-Feedback-Token": "guess"})).status_code == 403
    assert (await api.patch(f"/api/troubleshooting/feedback/{uuid.uuid4()}", json=change,
                            headers={"X-Feedback-Token": "x"})).status_code == 404
    assert (await feedback_summary(db_session, a.id)).counts.resolved == 1


async def test_knowledge_must_support_the_recommendation(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, b, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    r = await post(api, payload(sid, nodes["n3"], b))  # n3 is built from knowledge a only
    assert r.status_code == 422 and "not a source" in r.json()["detail"]
    r = await post(api, {**payload(sid, nodes["n3"], a), "knowledge_item_id": str(uuid.uuid4())})
    assert r.status_code == 422


async def test_session_and_step_references_are_validated(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    sid = await session_at_recommendation(api, guide.id)
    assert (await post(api, {**payload(sid, nodes["n3"], a), "troubleshooting_session_id": str(uuid.uuid4())})
            ).status_code == 404
    assert (await post(api, payload(sid, nodes["n2"], a))).status_code == 422  # a question, not a recommendation
    assert (await post(api, payload(sid, nodes["n5"], a))).status_code == 409  # not reached yet
    other = await generate(db_session, FakeEmbedder(), ScriptedGemini(expert_draft_from))
    foreign = await db_session.scalar(select(GuideNode).where(GuideNode.guide_id == other.id,
                                                              GuideNode.node_key == "n3"))
    assert (await post(api, payload(sid, foreign, a))).status_code == 422  # step of another guide
    assert (await api.get(f"/api/troubleshooting/sessions/{uuid.uuid4()}/feedback")).status_code == 404


# ---- aggregation ----------------------------------------------------------------------------


async def test_aggregation_counts_sessions_once_and_breaks_down_by_firmware(
    db_session: AsyncSession, api: httpx.AsyncClient
) -> None:
    a, _, guide, nodes = await setup(db_session)
    s1 = await session_at_recommendation(api, guide.id)
    await post(api, payload(s1, nodes["n3"], a, firmware_version="3.2"))
    # Same session also reports on the resolution step of the same knowledge: still one session.
    await api.post(f"/api/troubleshooting/sessions/{s1}/steps", json={"type": "answer", "answer_label": "Worked"})
    await post(api, payload(s1, nodes["n5"], a, firmware_version="3.2"))
    s2 = await session_at_recommendation(api, guide.id)
    await post(api, payload(s2, nodes["n3"], a, outcome="not_resolved", firmware_version="4.0"))
    s3 = await session_at_recommendation(api, guide.id)
    await post(api, payload(s3, nodes["n3"], a, outcome="partially_resolved"))

    summary = (await api.get(f"/api/knowledge/{a.id}/feedback/summary")).json()
    assert summary["sessions"] == 3 and summary["attempts"] == 3
    assert summary["counts"] == {"resolved": 1, "not_resolved": 1, "partially_resolved": 1, "unknown": 0,
                                 "not_attempted": 0}
    assert summary["has_conflicting_reports"] is True
    assert summary["success_rate"] is None and summary["min_sample_for_rate"] == MIN_SAMPLE_FOR_RATE
    firmware = {b["value"]: b["counts"] for b in summary["by_firmware"]}
    assert firmware["3.2"]["resolved"] == 1 and firmware["4.0"]["not_resolved"] == 1
    assert firmware[None]["partially_resolved"] == 1
    assert any("Firmware 4.0" in n and "not resolved" in n for n in summary["condition_notes"])

    records = (await api.get(f"/api/knowledge/{a.id}/feedback")).json()
    assert records["total"] == 4  # every record stays inspectable
    assert len((await api.get(f"/api/troubleshooting/sessions/{s1}/feedback")).json()) == 2


async def test_rate_only_from_minimum_sample(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    for i in range(MIN_SAMPLE_FOR_RATE):
        sid = await session_at_recommendation(api, guide.id)
        await post(api, payload(sid, nodes["n3"], a, outcome="resolved" if i else "not_resolved"))
    summary = await feedback_summary(db_session, a.id)
    assert summary.success_rate == round((MIN_SAMPLE_FOR_RATE - 1) / MIN_SAMPLE_FOR_RATE, 3)


# ---- where feedback shows up ----------------------------------------------------------------


async def test_feedback_never_changes_knowledge_status_and_is_a_separate_origin(
    db_session: AsyncSession, api: httpx.AsyncClient
) -> None:
    a, _, guide, nodes = await setup(db_session)
    for _ in range(3):
        await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a))
    detail = (await api.get(f"/api/knowledge/{a.id}")).json()
    assert detail["approval_status"] == ApprovalStatus.UNREVIEWED.value
    assert detail["resolution_status"] == ResolutionStatus.CONFIRMED_IN_CONVERSATION.value
    assert {e["origin"] for e in detail["evidence"]} == {"conversation"}
    assert len(detail["evidence"]) == 2  # original Slack/simulated evidence untouched, no fake messages
    feedback = (await api.get(f"/api/knowledge/{a.id}/feedback")).json()
    assert feedback["total"] == 3 and {f["origin"] for f in feedback["items"]} == {"troubleshooting_feedback"}


async def test_search_shows_feedback_without_changing_ranking(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, b, guide, nodes = await setup(db_session)
    query = {"query": "customer connections drop every half hour", "limit": 5}
    before = [r["id"] for r in (await api.post("/api/search", json=query)).json()["results"]]
    for outcome in ("resolved", "not_resolved"):
        await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a, outcome=outcome))
    results = (await api.post("/api/search", json=query)).json()["results"]
    assert [r["id"] for r in results] == before
    by_id = {r["id"]: r for r in results}
    assert by_id[str(a.id)]["feedback"]["counts"]["resolved"] == 1
    assert by_id[str(a.id)]["feedback"]["counts"]["not_resolved"] == 1
    assert by_id[str(b.id)]["feedback"] is None


async def test_future_guides_receive_feedback_context(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    a, _, guide, nodes = await setup(db_session)
    await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a, firmware_version="3.2"))
    await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a,
                            outcome="not_resolved", firmware_version="4.0"))
    gemini = ScriptedGemini(expert_draft_from)
    await generate(db_session, FakeEmbedder(), gemini, problem="Connections drop every half hour on firmware 4.0")
    prompt = gemini.prompts[0]
    assert '"troubleshooting_feedback"' in prompt and "self-reported" in prompt
    assert '"firmware": "4.0"' in prompt and '"not_resolved": 1' in prompt
    from app.services.guides.generator import SYSTEM_INSTRUCTION
    assert "SELF-REPORTED" in SYSTEM_INSTRUCTION and "never invent feedback" in SYSTEM_INSTRUCTION


# ---- consolidation and Gemini failures ------------------------------------------------------


async def test_group_summary_uses_feedback_and_gemini_outage_keeps_feedback(
    db_session: AsyncSession, api: httpx.AsyncClient
) -> None:
    a, b, guide, nodes = await setup(db_session)
    # Group the two cases (different outcomes) with the fake consolidation model.
    tag_titles = {a.id: "S42", b.id: "S17"}
    for item in (a, b):
        item.title = f"{tag_titles[item.id]}: {item.title}"
    await db_session.commit()
    fake = FakeConsolidationGemini({frozenset({"S42", "S17"}): Rule("different_outcome", outcome="different_outcome")})
    config = ConsolidationConfig(min_similarity=0.05)
    await consolidate_item(db_session, a.id, fake, config)
    assert fake.summary_calls, "group summary generated"

    await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a,
                            outcome="not_resolved", firmware_version="4.0"))
    fake.fail = GeminiUnavailableError("Gemini is temporarily unavailable (HTTP 503).")
    assert await refresh_group_for_item(db_session, a.id, fake, config) == "retry"
    assert (await feedback_summary(db_session, a.id)).counts.not_resolved == 1  # nothing lost
    group = (await api.get(f"/api/knowledge/{a.id}/related")).json()["group"]
    assert group["summary_pending"] is True

    fake.fail = None
    assert await refresh_group_for_item(db_session, a.id, fake, config) == "refreshed"
    assert '"troubleshooting_feedback"' in fake.summary_calls[-1] and '"firmware": "4.0"' in fake.summary_calls[-1]
    group = (await api.get(f"/api/knowledge/{a.id}/related")).json()["group"]
    assert group["summary_pending"] is False


async def test_feedback_is_saved_without_gemini(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    """The API's background refresh failing (no Gemini) never affects the saved feedback."""
    a, _, guide, nodes = await setup(db_session)

    class Broken:
        def schedule_feedback_refresh(self, item_id):
            raise RuntimeError("Gemini is not configured")

    app.state.discovery = Broken()  # restored by the recorder fixture
    r = await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a))
    assert r.status_code == 201
    assert (await feedback_summary(db_session, a.id)).counts.resolved == 1


async def test_dashboard_metrics_come_from_feedback(db_session: AsyncSession, api: httpx.AsyncClient) -> None:
    from app.services.discovery.overview import discovery_metrics

    a, _, guide, nodes = await setup(db_session)
    await post(api, payload(await session_at_recommendation(api, guide.id), nodes["n3"], a))
    sid = await session_at_recommendation(api, guide.id)
    await post(api, payload(sid, nodes["n3"], a, outcome="not_resolved"))
    await api.post(f"/api/troubleshooting/sessions/{sid}/complete", json={"outcome": "unresolved", "summary": "x"})
    metrics = await discovery_metrics(db_session)
    assert metrics.feedback_resolved == 1 and metrics.feedback_not_resolved == 1
    assert metrics.knowledge_with_conflicting_feedback == 1 and metrics.sessions_completed == 1
    assert metrics.knowledge_reused == 2  # both sources of the followed guide
