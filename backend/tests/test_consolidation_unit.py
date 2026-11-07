"""Validation of Gemini consolidation output (no database, no Gemini)."""

import uuid

from app.ai.consolidation_schema import ConditionDifference, GroupSummaryDraft, PairComparison, SolutionPath
from app.services.consolidation.validation import CaseView, validate_comparison, validate_summary

M = [uuid.uuid4() for _ in range(4)]
A = CaseView(uuid.uuid4(), {"A1": M[0], "A2": M[1]},
             "Site 42 drops every 20 minutes. Restarted the DHCP relay service, that worked. S42-RTR-01")
B = CaseView(uuid.uuid4(), {"B1": M[2], "B2": M[3]},
             "Site 17 on firmware 4.0 drops. Restarting the relay did not help; lease time fixed it. S17-RTR-02")


def comparison(**kw) -> PairComparison:
    base = dict(is_related=True, relationship_type="different_outcome", shared_symptoms=["drops"],
                shared_equipment=[], different_conditions=[], unknown_conditions=[],
                outcome_comparison="different_outcome", explanation="Restart worked in A, not in B.",
                first_evidence_refs=["A2"], second_evidence_refs=["B2"])
    base.update(kw)
    return PairComparison(**base)


def test_valid_comparison_maps_labels_to_message_ids() -> None:
    valid = validate_comparison(comparison(), A, B)
    assert valid.relationship_type == "different_outcome" and valid.groups_together
    assert valid.first_evidence_ids == [M[1]] and valid.second_evidence_ids == [M[3]]
    assert valid.notes == []


def test_evidence_of_the_wrong_case_is_rejected_and_relationship_downgraded() -> None:
    valid = validate_comparison(comparison(first_evidence_refs=["B1", "A9"], second_evidence_refs=["A1"]), A, B)
    assert valid.first_evidence_ids == [] and valid.second_evidence_ids == []
    assert valid.relationship_type == "related_symptoms" and not valid.groups_together
    assert len([n for n in valid.notes if "Ignored evidence" in n]) == 3


def test_invented_condition_values_become_unknown() -> None:
    raw = comparison(different_conditions=[
        ConditionDifference(field="firmware", first_value="3.2", second_value="4.0"),  # 3.2 not in A
        ConditionDifference(field="vendor", first_value="Acme", second_value="Bolt"),  # neither stated
    ])
    valid = validate_comparison(raw, A, B)
    assert valid.conditions == [{"field": "firmware", "first_value": None, "second_value": "4.0"}]
    assert "vendor" in valid.unknown_conditions
    assert any("not stated in case A" in n for n in valid.notes)


def test_equal_conditions_are_not_differences_and_unknowns_are_kept() -> None:
    raw = comparison(unknown_conditions=["router model"], different_conditions=[
        ConditionDifference(field="symptom", first_value="drops", second_value="drops")])
    valid = validate_comparison(raw, A, B)
    assert valid.conditions == [] and valid.unknown_conditions == ["router model"]


def test_shared_equipment_must_appear_in_both_cases() -> None:
    valid = validate_comparison(comparison(shared_equipment=["S42-RTR-01"]), A, B)
    assert valid.shared_equipment == []


def test_unrelated_pairs_carry_no_evidence() -> None:
    valid = validate_comparison(comparison(is_related=False), A, B)
    assert valid.relationship_type == "unrelated" and valid.outcome_comparison == "not_comparable"
    assert valid.first_evidence_ids == valid.second_evidence_ids == []


def test_summary_drops_unknown_cases_and_ungrounded_details() -> None:
    k1, k2 = uuid.uuid4(), uuid.uuid4()
    draft = GroupSummaryDraft(
        title="Connection drops", shared_problem="Customers lose sessions", shared_symptoms=["drops"],
        known_environment=["firmware 4.0", "firmware 5.1"],
        solutions=[
            SolutionPath(description="Restart DHCP relay", outcome="mixed", conditions=["on firmware 4.0: failed"],
                         case_refs=["K1", "K2", "K7"]),
            SolutionPath(description="Invented path", outcome="successful", conditions=[], case_refs=["K9"]),
            SolutionPath(description="Fix lease time", outcome="successful", conditions=["firmware 4.1"],
                         case_refs=["K2"]),
        ],
        failed_attempts=["Relay restart on firmware 4.0"], contradictions=["Restart worked in K1, not in K2"],
        missing_information=["Firmware of Site 42"],
    )
    valid = validate_summary(draft, {"K1": k1, "K2": k2}, A.corpus + "\n" + B.corpus)
    assert valid.known_environment == ["firmware 4.0"]
    assert [s["description"] for s in valid.solutions] == ["Restart DHCP relay", "Fix lease time"]
    assert valid.solutions[0]["knowledge_ids"] == [str(k1), str(k2)]
    assert valid.solutions[1]["conditions"] == []  # "4.1" is not in any case
    assert valid.missing_information == ["Firmware of Site 42"]
    assert len(valid.notes) >= 4
