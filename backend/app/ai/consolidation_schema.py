"""Structured outputs for knowledge consolidation (pair comparison and group summary).

Evidence is referenced by per-request labels (A1, B2 for a pair; K1 for group members);
the server maps labels back and rejects anything that is not part of the request.
"""

from typing import Literal

from pydantic import BaseModel, Field

RelationshipType = Literal[
    "same_problem",
    "supporting_evidence",
    "same_problem_different_conditions",
    "different_outcome",
    "potentially_conflicting",
    "related_symptoms",
    "unrelated",
]


class ConditionDifference(BaseModel):
    field: str = Field(description="e.g. firmware, equipment model, vendor, configuration, site, service.")
    first_value: str | None = Field(description="Value for case A copied from its text, or null if unknown.")
    second_value: str | None = Field(description="Value for case B copied from its text, or null if unknown.")


class PairComparison(BaseModel):
    is_related: bool
    relationship_type: RelationshipType = Field(
        description=(
            "same_problem: same underlying problem and fix; supporting_evidence: B independently "
            "confirms A's fix; same_problem_different_conditions: same problem, different equipment/"
            "firmware/config; different_outcome: same action, different result; potentially_conflicting: "
            "recommendations contradict; related_symptoms: only symptoms overlap; unrelated."
        )
    )
    shared_symptoms: list[str]
    shared_equipment: list[str] = Field(description="Identifiers that appear in BOTH cases, copied exactly.")
    different_conditions: list[ConditionDifference]
    unknown_conditions: list[str] = Field(
        description="Conditions that matter but are not stated for one or both cases (never assume they match)."
    )
    outcome_comparison: Literal["same_outcome", "different_outcome", "not_comparable"]
    explanation: str = Field(description="Two sentences at most, citing what each case reported.")
    first_evidence_refs: list[str] = Field(description="Labels of A's messages supporting this, e.g. A2.")
    second_evidence_refs: list[str] = Field(description="Labels of B's messages supporting this, e.g. B1.")
    replaced_case: Literal["A", "B", "none"] = Field(
        default="none",
        description=(
            "Set only if the NEWER case explicitly says the other case's information or advice is no "
            "longer valid (e.g. a lock was replaced, a procedure changed). The value is the OUTDATED "
            "case. Different outcomes or conditions alone are not replacement."
        ),
    )


class SolutionPath(BaseModel):
    description: str = Field(description="The action, as reported.")
    outcome: Literal["successful", "unsuccessful", "mixed", "unknown"]
    conditions: list[str] = Field(description="Conditions under which it was reported (copied, not guessed).")
    case_refs: list[str] = Field(description="Labels of the cases reporting it, e.g. K1, K3.")


class GroupSummaryDraft(BaseModel):
    title: str = Field(description="Short name of the shared problem.")
    shared_problem: str
    shared_symptoms: list[str]
    known_environment: list[str] = Field(description="Equipment, firmware, sites as stated in the cases.")
    solutions: list[SolutionPath]
    failed_attempts: list[str]
    contradictions: list[str]
    missing_information: list[str]
