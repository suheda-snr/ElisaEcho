"""Guide validation: graph structure, evidence references, derived approval (no DB, no Gemini)."""

import uuid

import httpx
import pytest
from pydantic import ValidationError

from app.ai.guide_schema import GuideDraft
from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    GuideNodeType,
    ResolutionStatus,
    SupportLevel,
)
from app.services.guides.validation import (
    ContextEvidence,
    ContextKnowledge,
    GuideContext,
    GuideValidationError,
    validate_guide,
)
from tests.guide_fakes import draft, edge, node, two_expert_draft

K1, K2 = uuid.uuid4(), uuid.uuid4()
M = [uuid.uuid4() for _ in range(4)]


def context(k1_approval=ApprovalStatus.UNREVIEWED, k2_status=ResolutionStatus.CONFIRMED_IN_CONVERSATION) -> GuideContext:
    return GuideContext(
        knowledge={
            "K1": ContextKnowledge(K1, ResolutionStatus.CONFIRMED_IN_CONVERSATION, k1_approval),
            "K2": ContextKnowledge(K2, k2_status, ApprovalStatus.UNREVIEWED),
        },
        evidence={
            "E1": ContextEvidence(M[0], K1, EvidenceType.PROBLEM_REPORT),
            "E2": ContextEvidence(M[1], K1, EvidenceType.CONFIRMED_RESOLUTION),
            "E3": ContextEvidence(M[2], K2, EvidenceType.PROBLEM_REPORT),
            "E4": ContextEvidence(M[3], K2, EvidenceType.CONFIRMED_RESOLUTION),
        },
    )


def problems(d) -> list[str]:
    with pytest.raises(GuideValidationError) as exc_info:
        validate_guide(d, context())
    return exc_info.value.problems


def test_valid_guide_with_two_expert_branches() -> None:
    guide = validate_guide(two_expert_draft(), context())
    by_key = {n.key: n for n in guide.nodes}
    assert set(guide.knowledge_ids) == {K1, K2}
    # Alternatives stay separate branches with their own sources.
    assert by_key["n3"].knowledge_ids == [K1] and by_key["n4"].knowledge_ids == [K2]
    assert by_key["n2"].expected_answers == ["No", "Yes, did not help"]  # derived from real edges
    assert [e.message_id for e in by_key["n3"].evidence] == [M[0], M[1]]
    assert guide.conflicts and guide.uncertainties


def test_approval_and_support_are_derived_not_trusted() -> None:
    guide = validate_guide(two_expert_draft(), context())
    by_key = {n.key: n for n in guide.nodes}
    assert by_key["n3"].approval_status is ApprovalStatus.UNREVIEWED
    assert by_key["n3"].support_level is SupportLevel.CONFIRMED_IN_CONVERSATION
    assert by_key["n3"].requires_manual_verification is True
    assert by_key["n4"].support_level is SupportLevel.CONFLICTING  # conflict note -> flagged
    assert by_key["n1"].support_level is SupportLevel.NONE and by_key["n1"].requires_manual_verification is False

    approved = validate_guide(two_expert_draft(), context(k1_approval=ApprovalStatus.APPROVED))
    n3 = next(n for n in approved.nodes if n.key == "n3")
    assert n3.approval_status is ApprovalStatus.APPROVED and n3.support_level is SupportLevel.APPROVED
    assert n3.requires_manual_verification is False


def test_navigation_steps_get_no_support_label_even_with_evidence() -> None:
    d = two_expert_draft()
    d.nodes[0].evidence_refs = ["E1", "E3"]  # model attached context to the start step
    d.nodes[6].evidence_refs = ["E2"]  # and to the escalation
    guide = validate_guide(d, context())
    by_key = {n.key: n for n in guide.nodes}
    for key in ("n1", "n7"):
        assert by_key[key].support_level is SupportLevel.NONE and by_key[key].approval_status is None
        assert by_key[key].evidence  # still shown as context
        assert by_key[key].requires_manual_verification is False


def test_suggested_knowledge_is_labelled_suggested() -> None:
    guide = validate_guide(two_expert_draft(), context(k2_status=ResolutionStatus.SUGGESTED))
    n6 = next(n for n in guide.nodes if n.key == "n6")
    assert n6.support_level is SupportLevel.SUGGESTED


def test_unknown_evidence_references_are_ignored_and_noted() -> None:
    d = two_expert_draft()
    d.nodes[2].evidence_refs = ["E1", "E2", "E99"]
    d.nodes[2].knowledge_refs = ["K1", "K7"]
    guide = validate_guide(d, context())
    n3 = next(n for n in guide.nodes if n.key == "n3")
    assert [e.message_id for e in n3.evidence] == [M[0], M[1]] and n3.knowledge_ids == [K1]
    assert any("E99" in note for note in guide.notes) and any("K7" in note for note in guide.notes)


def test_same_message_under_two_labels_is_cited_once() -> None:
    ctx = context()
    # The confirming message also has an "attempted fix" role -> second label, same message.
    ctx.evidence["E5"] = ContextEvidence(M[1], K1, EvidenceType.ATTEMPTED_FIX)
    d = two_expert_draft()
    d.nodes[2].evidence_refs = ["E1", "E2", "E5"]
    n3 = next(n for n in validate_guide(d, ctx).nodes if n.key == "n3")
    assert [e.message_id for e in n3.evidence] == [M[0], M[1]]


def test_recommendation_without_valid_evidence_is_rejected() -> None:
    d = two_expert_draft()
    d.nodes[2].evidence_refs = ["E42"]  # only invented evidence
    assert any("cites no valid source message" in p for p in problems(d))


@pytest.mark.parametrize(("nodes", "edges", "expected"), [
    ([node("a", "start"), node("b", "escalation")], [edge("a", "zzz", "Go")], "does not exist"),
    ([node("a", "start"), node("b", "escalation")], [edge("a", "a", "Loop"), edge("a", "b", "Go")], "itself"),
    ([node("a", "start"), node("b", "question", question="?"), node("c", "escalation")],
     [edge("a", "b", "Go"), edge("b", "a", "Back"), edge("b", "c", "End")], "loop"),
    ([node("a", "start"), node("b", "escalation"), node("c", "escalation")], [edge("a", "b", "Go")], "not reachable"),
    ([node("a", "start"), node("b", "start"), node("c", "escalation")],
     [edge("a", "c", "Go"), edge("b", "c", "Go")], "Exactly one start"),
    ([node("a", "start"), node("b", "question", question="Q?"), node("c", "escalation")],
     [edge("a", "b", "Go"), edge("b", "c", "Yes")], "at least two answers"),
    ([node("a", "start"), node("b", "escalation"), node("c", "resolution", e=["E1"])],
     [edge("a", "b", "Go"), edge("a", "c", "Fixed"), edge("b", "c", "Then")], "end point"),
    ([node("a", "start"), node("b", "diagnostic", e=["E1"])], [edge("a", "b", "Go")], "dead end"),
    ([node("a", "start"), node("b", "escalation")], [edge("a", "b", "Go"), edge("a", "b", "go")], "twice"),
])
def test_invalid_graphs_are_rejected(nodes, edges, expected) -> None:
    found = problems(draft(nodes, edges))
    assert any(expected.lower() in p.lower() for p in found), found


def test_duplicate_node_ids_and_size_limits() -> None:
    with pytest.raises(GuideValidationError):
        validate_guide(draft([node("a", "start"), node("a", "escalation")], [edge("a", "a", "x")]), context())
    with pytest.raises(GuideValidationError):
        validate_guide(draft([node("a", "start")], []), context())


def test_malformed_model_output_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        GuideDraft.model_validate({"title": "x", "nodes": [{"id": "n1", "node_type": "magic"}]})


def test_node_types_cover_spec() -> None:
    assert {t.value for t in GuideNodeType} == {
        "start", "question", "diagnostic", "recommendation", "resolution", "escalation"}


@pytest.mark.parametrize("body", [{"problem": "abc"}, {"problem": "x" * 1001}, {},
                                  {"problem": "Connection drops", "equipment_identifier": "x" * 101}])
async def test_generate_request_validation(client_without_db_access: httpx.AsyncClient, body: dict) -> None:
    assert (await client_without_db_access.post("/api/guides/generate", json=body)).status_code == 422


@pytest.mark.parametrize("body", [{"type": "jump"}, {"type": "answer", "answer_label": ""},
                                  {"type": "observation", "observation": "x" * 2001}])
async def test_step_request_validation(client_without_db_access: httpx.AsyncClient, body: dict) -> None:
    url = f"/api/troubleshooting/sessions/{uuid.uuid4()}/steps"
    assert (await client_without_db_access.post(url, json=body)).status_code == 422


async def test_complete_request_requires_valid_outcome(client_without_db_access: httpx.AsyncClient) -> None:
    url = f"/api/troubleshooting/sessions/{uuid.uuid4()}/complete"
    response = await client_without_db_access.post(url, json={"outcome": "maybe", "summary": "x"})
    assert response.status_code == 422
