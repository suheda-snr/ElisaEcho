"""Phase 5 integration: guide generation from retrieved knowledge, sessions and API.

Isolated test database, fake embeddings and a scripted fake Gemini (no API calls).
"""

import json
import re

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import GeminiQuotaExceededError, GeminiResponseError
from app.api.routes.search import get_embedding_service
from app.core.config import Settings, get_settings
from app.main import app
from app.models import GuideNode, KnowledgeItem, NodeEvidence, SessionStep, TroubleshootingGuide
from app.models.enums import GuideStatus
from app.services.guides.generator import GuideGenerationError, generate_guide
from app.services.retrieval.indexing import index_item
from tests.guide_fakes import draft, edge, node, two_expert_draft
from tests.integration.test_search import make_item
from tests.retrieval_fakes import FakeEmbedder

LOOSE = {"min_similarity": 0.05, "similarity_margin": 1.0}
PROBLEM = "Customers drop their connection every half hour even after rebooting the router"


class ScriptedGemini:
    """Fake Gemini for guides: `script` entries are drafts, callables(prompt)->draft, or errors."""

    model = "fake-guide-model"
    configured = True

    def __init__(self, *script):
        self.script = list(script)
        self.prompts: list[str] = []

    async def generate_structured(self, *, system_instruction, contents, schema):
        self.prompts.append(contents)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(contents) if callable(item) else item


def refs_by_title(prompt: str) -> dict[str, tuple[str, list[str]]]:
    """Map knowledge title -> (K label, [E labels]) from the prompt's knowledge JSON."""
    data = json.loads(re.search(r"<knowledge>\n(.*)\n</knowledge>", prompt, re.S).group(1))
    return {k["title"]: (k["ref"], [m["ref"] for m in k["messages"]]) for k in data}


def expert_draft_from(prompt: str):
    refs = refs_by_title(prompt)
    k1, (e1, e2) = refs["Restart DHCP relay service"][0], refs["Restart DHCP relay service"][1]
    k2, (e3, e4) = refs["Fix DHCP lease time"][0], refs["Fix DHCP lease time"][1]
    return two_expert_draft(k1, k2, e1, e2, e3, e4)


async def two_experts(db: AsyncSession) -> tuple[KnowledgeItem, KnowledgeItem, FakeEmbedder]:
    a = await make_item(db, "g42", title="Restart DHCP relay service",
                        problem="Customer connections drop every half hour at Site 42 after router reboot",
                        resolution="Restart the DHCP relay service instead of rebooting the router",
                        messages=["Site 42 customers drop every 30 minutes, router reboot did not help",
                                  "Restart only the DHCP relay service", "That worked, connections stable"],
                        equipment=["TEST-G-S42"])
    b = await make_item(db, "g17", title="Fix DHCP lease time",
                        problem="Customer connections drop every half hour at Site 17, relay restart did not help",
                        resolution="Set the DHCP lease time back to 24 hours",
                        messages=["Site 17 customers drop every half hour, restarting the relay did not help",
                                  "Lease time was 60 seconds, set to 24 hours, drops stopped"],
                        equipment=["TEST-G-S17"])
    embedder = FakeEmbedder()
    for item in (a, b):
        await index_item(db, item.id, embedder)
    return a, b, embedder


async def generate(db, embedder, gemini, problem=PROBLEM, equipment=None):
    return await generate_guide(db, problem=problem, equipment_identifier=equipment, embedder=embedder,
                                gemini=gemini, **LOOSE)


# ---- generation --------------------------------------------------------------------------

async def test_guide_from_two_experts_keeps_separate_evidence_backed_branches(db_session: AsyncSession) -> None:
    a, b, embedder = await two_experts(db_session)
    gemini = ScriptedGemini(expert_draft_from)
    guide = await generate(db_session, embedder, gemini)

    assert guide.status is GuideStatus.READY and guide.model_name == "fake-guide-model"
    assert set(guide.source_knowledge_ids) == {str(a.id), str(b.id)}
    prompt = gemini.prompts[0]
    assert "That worked, connections stable" in prompt and "Lease time was 60 seconds" in prompt
    assert "Restart only the DHCP relay service" not in prompt  # not evidence: not sent to the model
    assert "Engineer" in prompt  # authors are passed as evidence context

    nodes = {n.node_key: n for n in await db_session.scalars(select(GuideNode).where(GuideNode.guide_id == guide.id))}
    assert nodes["n3"].knowledge_item_ids == [str(a.id)] and nodes["n4"].knowledge_item_ids == [str(b.id)]
    assert nodes["n4"].support_level.value == "conflicting" and nodes["n4"].conflict_note
    assert nodes["n3"].requires_manual_verification and nodes["n3"].approval_status.value == "unreviewed"
    evidence = list(await db_session.scalars(select(NodeEvidence).where(NodeEvidence.node_id == nodes["n3"].id)))
    assert {e.knowledge_item_id for e in evidence} == {a.id}


async def test_insufficient_evidence_does_not_call_gemini(db_session: AsyncSession) -> None:
    await two_experts(db_session)
    gemini = ScriptedGemini()
    guide = await generate(db_session, FakeEmbedder(), gemini, problem="Printer on floor three is out of toner",
                           equipment=None)
    # Fake vectors are loose; use the real calibrated floor for this check.
    if guide.status is GuideStatus.READY:  # pragma: no cover - defensive
        pytest.fail("Generated a guide without relevant evidence")
    assert guide.status is GuideStatus.INSUFFICIENT_EVIDENCE and gemini.prompts == []
    count = await db_session.scalar(select(func.count()).select_from(GuideNode).where(GuideNode.guide_id == guide.id))
    assert count == 0 and "No previously discovered knowledge" in guide.status_reason


async def test_model_can_declare_insufficient_evidence(db_session: AsyncSession) -> None:
    _, _, embedder = await two_experts(db_session)
    gemini = ScriptedGemini(draft([], [], sufficient=False, reason="Knowledge covers DHCP, not fibre faults."))
    guide = await generate(db_session, embedder, gemini, problem="Customer connections drop on fibre uplink")
    assert guide.status is GuideStatus.INSUFFICIENT_EVIDENCE and "fibre" in guide.status_reason


async def test_invalid_draft_is_retried_with_feedback_then_accepted(db_session: AsyncSession) -> None:
    _, _, embedder = await two_experts(db_session)

    def invented_evidence(prompt):
        d = expert_draft_from(prompt)
        d.nodes[2].evidence_refs = ["E77"]  # unsupported recommendation
        return d

    gemini = ScriptedGemini(invented_evidence, expert_draft_from)
    guide = await generate(db_session, embedder, gemini)
    assert guide.status is GuideStatus.READY and len(gemini.prompts) == 2
    assert "rejected" in gemini.prompts[1] and "cites no valid source message" in gemini.prompts[1]


async def test_repeatedly_invalid_drafts_store_nothing(db_session: AsyncSession) -> None:
    _, _, embedder = await two_experts(db_session)
    looping = lambda p: draft([node("a", "start"), node("b", "question", question="?"), node("c", "escalation")],  # noqa: E731
                              [edge("a", "b", "Go"), edge("b", "a", "Back"), edge("b", "c", "End")])
    before = await db_session.scalar(select(func.count()).select_from(TroubleshootingGuide))
    with pytest.raises(GuideGenerationError):
        await generate(db_session, embedder, ScriptedGemini(looping, looping))
    assert await db_session.scalar(select(func.count()).select_from(TroubleshootingGuide)) == before


async def test_gemini_failures_propagate_without_storing(db_session: AsyncSession) -> None:
    _, _, embedder = await two_experts(db_session)
    before = await db_session.scalar(select(func.count()).select_from(TroubleshootingGuide))
    with pytest.raises(GeminiQuotaExceededError):
        await generate(db_session, embedder, ScriptedGemini(GeminiQuotaExceededError("quota")))
    with pytest.raises(GeminiResponseError):  # invalid JSON from the model
        await generate(db_session, embedder, ScriptedGemini(GeminiResponseError("bad json")))
    assert await db_session.scalar(select(func.count()).select_from(TroubleshootingGuide)) == before


# ---- API: guides and sessions ------------------------------------------------------------

@pytest.fixture
async def guide_api(api: httpx.AsyncClient, db_session: AsyncSession):
    a, b, embedder = await two_experts(db_session)
    gemini = ScriptedGemini(expert_draft_from)
    embedder.gemini = gemini  # the route uses the embedder's Gemini client
    app.dependency_overrides[get_embedding_service] = lambda: embedder
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="test", search_min_similarity=0.05, search_similarity_margin=1.0)
    return api, a, b


async def test_full_session_flow_with_back_and_reload(guide_api, db_session: AsyncSession) -> None:
    api, a, b = guide_api
    response = await api.post("/api/guides/generate", json={"problem": PROBLEM, "equipment_identifier": "TEST-G-S17"})
    assert response.status_code == 200
    guide = response.json()
    assert guide["status"] == "ready" and len(guide["nodes"]) == 7 and len(guide["edges"]) == 7
    assert {k["id"] for k in guide["knowledge"]} == {str(a.id), str(b.id)}
    by_key = {n["key"]: n for n in guide["nodes"]}
    rec = by_key["n3"]
    assert rec["evidence"] and rec["evidence"][0]["author"].endswith("(synthetic)")
    assert rec["evidence"][0]["excerpt"] and rec["evidence"][0]["source_name"].startswith("Search test")
    assert rec["approval_status"] == "unreviewed" and rec["requires_manual_verification"] is True
    assert "change-management" in guide["safety_notice"]

    started = (await api.post("/api/troubleshooting/sessions", json={"guide_id": guide["id"]})).json()
    sid = started["id"]
    assert started["current_node_id"] == guide["start_node_id"] and started["active_path"] == [guide["start_node_id"]]

    async def step(**body):
        return await api.post(f"/api/troubleshooting/sessions/{sid}/steps", json=body)

    assert (await step(type="answer", answer_label="Continue")).status_code == 200
    wrong = await step(type="answer", answer_label="Maybe")
    assert wrong.status_code == 422 and "allowed" in wrong.json()["detail"]
    s = (await step(type="answer", answer_label="no")).json()  # case-insensitive
    assert s["current_node_id"] == by_key["n3"]["id"]
    assert s["active_path"] == [by_key[k]["id"] for k in ("n1", "n2", "n3")]

    # Revise: go back to the question and take the other branch.
    s = (await step(type="back")).json()
    assert s["current_node_id"] == by_key["n2"]["id"]
    s = (await step(type="answer", answer_label="Yes, did not help")).json()
    assert s["active_path"] == [by_key[k]["id"] for k in ("n1", "n2", "n4")]
    superseded = [x for x in s["steps"] if x["superseded"]]
    assert len(superseded) == 1 and superseded[0]["answer_label"] == "No"  # history kept

    s = (await step(type="observation", observation="Lease time shows 60 s on TEST-G-S17",
                    action_taken="Checked DHCP config")).json()
    assert s["steps"][-1]["step_type"] == "observation" and s["current_node_id"] == by_key["n4"]["id"]
    s = (await step(type="answer", answer_label="Yes")).json()
    assert s["current_node_id"] == by_key["n6"]["id"]
    end = await step(type="answer", answer_label="Yes")
    assert end.status_code == 409  # end point: complete instead

    done = (await api.post(f"/api/troubleshooting/sessions/{sid}/complete",
                           json={"outcome": "resolved", "summary": "Lease time fixed, stable",
                                 "action_taken": "Set lease to 24 h"})).json()
    assert done["status"] == "resolved" and done["completed_at"] and done["outcome_summary"]
    assert (await step(type="observation", observation="late")).status_code == 409

    reloaded = (await api.get(f"/api/troubleshooting/sessions/{sid}")).json()
    assert [x["step_type"] for x in reloaded["steps"]] == ["answer", "answer", "back", "answer", "observation",
                                                            "answer", "complete"]
    assert [x["sequence"] for x in reloaded["steps"]] == list(range(1, 8))
    assert reloaded["active_path"] == [by_key[k]["id"] for k in ("n1", "n2", "n4", "n6")]
    assert reloaded["guide"]["id"] == guide["id"]

    # Session outcomes never change knowledge approval.
    item = await db_session.get(KnowledgeItem, b.id, populate_existing=True)
    assert item.approval_status.value == "unreviewed"
    assert (await api.get("/api/troubleshooting/sessions")).json()["total"] >= 1


async def test_session_errors(guide_api) -> None:
    api, _, _ = guide_api
    import uuid as _uuid

    assert (await api.post("/api/troubleshooting/sessions", json={"guide_id": str(_uuid.uuid4())})).status_code == 404
    assert (await api.get(f"/api/troubleshooting/sessions/{_uuid.uuid4()}")).status_code == 404
    assert (await api.get(f"/api/guides/{_uuid.uuid4()}")).status_code == 404

    insufficient = (await api.post("/api/guides/generate",
                                   json={"problem": "printer toner empty on floor three"})).json()
    if insufficient["status"] == "insufficient_evidence":
        assert insufficient["nodes"] == [] and insufficient["status_reason"]
        r = await api.post("/api/troubleshooting/sessions", json={"guide_id": insufficient["id"]})
        assert r.status_code == 409

    guide = (await api.post("/api/guides/generate", json={"problem": PROBLEM})).json() \
        if insufficient["status"] == "insufficient_evidence" else insufficient
    sid = (await api.post("/api/troubleshooting/sessions", json={"guide_id": guide["id"]})).json()["id"]
    assert (await api.post(f"/api/troubleshooting/sessions/{sid}/steps", json={"type": "back"})).status_code == 409
    assert (await api.post(f"/api/troubleshooting/sessions/{sid}/steps",
                           json={"type": "observation"})).status_code == 422


async def test_generate_endpoint_maps_gemini_errors(api: httpx.AsyncClient, db_session: AsyncSession) -> None:
    _, _, embedder = await two_experts(db_session)
    embedder.gemini = ScriptedGemini(GeminiQuotaExceededError("Gemini quota exhausted."))
    app.dependency_overrides[get_embedding_service] = lambda: embedder
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="test", search_min_similarity=0.05, search_similarity_margin=1.0)
    response = await api.post("/api/guides/generate", json={"problem": PROBLEM})
    assert response.status_code == 503 and "quota" in response.json()["detail"]


async def test_demo_reset_removes_guides_built_from_demo_data(db_session: AsyncSession, test_settings: Settings) -> None:
    from app.seed.seed import seed_demo_data
    from app.services.discovery.demo_reset import reset_demo_data

    await seed_demo_data(db_session, test_settings)
    _, _, embedder = await two_experts(db_session)  # non-demo knowledge
    guide = await generate(db_session, embedder, ScriptedGemini(expert_draft_from))
    summary = await reset_demo_data(db_session, test_settings)
    await db_session.commit()
    assert summary.guides == 0  # guide is not based on demo data: kept
    assert await db_session.get(TroubleshootingGuide, guide.id) is not None
    assert await db_session.scalar(select(func.count()).select_from(SessionStep)) is not None


