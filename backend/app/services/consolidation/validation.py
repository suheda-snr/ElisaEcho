"""Server-side checks on Gemini consolidation output (pure functions, no I/O).

- Evidence labels must belong to the case they are cited for.
- Condition values (firmware, models, ...) must literally appear in that case's own sources;
  otherwise they become unknown (None), never assumed.
- Shared equipment must appear in both cases.
- Grouping-strength relationships need valid evidence on both sides, else they are downgraded
  to `related_symptoms` (shown as a suggestion, never grouped).
"""

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.ai.consolidation_schema import GroupSummaryDraft, PairComparison

# Relationships strong enough to put two items in the same group.
GROUPING_TYPES = frozenset({
    "same_problem",
    "supporting_evidence",
    "same_problem_different_conditions",
    "different_outcome",
    "potentially_conflicting",
})
CONFLICT_TYPES = frozenset({"different_outcome", "potentially_conflicting"})


@dataclass
class CaseView:
    """What the server knows about one case: its evidence labels and its own source text."""

    knowledge_id: uuid.UUID
    evidence: Mapping[str, uuid.UUID]  # label ("A1") -> message id
    corpus: str  # knowledge fields + evidence excerpts, used to verify copied values
    latest_at: datetime | None = None  # newest evidence message (who is newer?)


@dataclass
class ValidComparison:
    relationship_type: str
    outcome_comparison: str
    explanation: str
    shared_symptoms: list[str]
    shared_equipment: list[str]
    conditions: list[dict[str, Any]]  # {"field", "first_value", "second_value"}
    unknown_conditions: list[str]
    first_evidence_ids: list[uuid.UUID]
    second_evidence_ids: list[uuid.UUID]
    notes: list[str] = field(default_factory=list)
    # "first" or "second": that case is outdated, replaced by the other one.
    superseded: str | None = None

    @property
    def groups_together(self) -> bool:
        return self.relationship_type in GROUPING_TYPES


def _present(value: str, corpus: str) -> bool:
    return " ".join(value.lower().split()) in " ".join(corpus.lower().split())


_SPECIFIC = re.compile(r"[A-Za-z]*\d[\w.\-]*")


def _grounded(text: str, corpus: str) -> bool:
    """Free text may be rephrased, but every specific token (versions, IDs: anything with a
    digit) must appear in the sources."""
    lowered = corpus.lower()
    return all(token.lower().strip(".-") in lowered for token in _SPECIFIC.findall(text))


def _clean(values: Sequence[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        v = v.strip()
        if v and v.lower() not in {o.lower() for o in out}:
            out.append(v)
    return out


def validate_comparison(raw: PairComparison, first: CaseView, second: CaseView) -> ValidComparison:
    notes: list[str] = []

    def resolve(refs: Sequence[str], case: CaseView, side: str) -> list[uuid.UUID]:
        ids: list[uuid.UUID] = []
        for ref in refs:
            message_id = case.evidence.get(ref.strip())
            if message_id is None:
                notes.append(f"Ignored evidence reference {ref!r} (not a message of case {side}).")
            elif message_id not in ids:
                ids.append(message_id)
        return ids

    first_ids = resolve(raw.first_evidence_refs, first, "A")
    second_ids = resolve(raw.second_evidence_refs, second, "B")

    conditions: list[dict[str, Any]] = []
    unknown = _clean(raw.unknown_conditions)
    for diff in raw.different_conditions:
        name = diff.field.strip()
        if not name:
            continue
        a = diff.first_value.strip() if diff.first_value and diff.first_value.strip() else None
        b = diff.second_value.strip() if diff.second_value and diff.second_value.strip() else None
        if a and not _present(a, first.corpus):
            notes.append(f"{name} value {a!r} is not stated in case A; recorded as unknown.")
            a = None
        if b and not _present(b, second.corpus):
            notes.append(f"{name} value {b!r} is not stated in case B; recorded as unknown.")
            b = None
        if a is None and b is None:
            if name.lower() not in {u.lower() for u in unknown}:
                unknown.append(name)
            continue
        if a is not None and b is not None and a.lower() == b.lower():
            continue  # not actually different
        conditions.append({"field": name, "first_value": a, "second_value": b})

    shared_equipment = []
    for ident in _clean(raw.shared_equipment):
        if _present(ident, first.corpus) and _present(ident, second.corpus):
            shared_equipment.append(ident)
        else:
            notes.append(f"Shared equipment {ident!r} does not appear in both cases; ignored.")

    relationship = raw.relationship_type if raw.is_related else "unrelated"
    if relationship in GROUPING_TYPES and (not first_ids or not second_ids):
        notes.append("No valid evidence on both sides; downgraded to related symptoms.")
        relationship = "related_symptoms"
    if relationship == "unrelated":
        first_ids, second_ids = [], []

    superseded = None
    if raw.replaced_case in ("A", "B"):
        old, new = (first, second) if raw.replaced_case == "A" else (second, first)
        if relationship == "unrelated" or not first_ids or not second_ids:
            notes.append("Replacement claim ignored: needs related cases with evidence on both sides.")
        elif old.latest_at is None or new.latest_at is None or new.latest_at <= old.latest_at:
            notes.append("Replacement claim ignored: the replacing case is not newer than the replaced one.")
        else:
            superseded = "first" if raw.replaced_case == "A" else "second"

    return ValidComparison(
        relationship_type=relationship,
        outcome_comparison=raw.outcome_comparison if relationship != "unrelated" else "not_comparable",
        explanation=raw.explanation.strip()[:1000],
        shared_symptoms=_clean(raw.shared_symptoms),
        shared_equipment=shared_equipment,
        conditions=conditions,
        unknown_conditions=unknown,
        first_evidence_ids=first_ids,
        second_evidence_ids=second_ids,
        notes=notes,
        superseded=superseded,
    )


@dataclass
class ValidSummary:
    title: str
    shared_problem: str
    shared_symptoms: list[str]
    known_environment: list[str]
    solutions: list[dict[str, Any]]  # {"description", "outcome", "conditions", "knowledge_ids"}
    failed_attempts: list[str]
    contradictions: list[str]
    missing_information: list[str]
    notes: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title, "shared_problem": self.shared_problem, "shared_symptoms": self.shared_symptoms,
            "known_environment": self.known_environment, "solutions": self.solutions,
            "failed_attempts": self.failed_attempts, "contradictions": self.contradictions,
            "missing_information": self.missing_information, "notes": self.notes,
        }


def validate_summary(raw: GroupSummaryDraft, members: Mapping[str, uuid.UUID], corpus: str) -> ValidSummary:
    notes: list[str] = []
    solutions = []
    for path in raw.solutions:
        ids = []
        for ref in path.case_refs:
            kid = members.get(ref.strip())
            if kid is None:
                notes.append(f"Ignored case reference {ref!r}.")
            elif str(kid) not in ids:
                ids.append(str(kid))
        if not ids:
            notes.append(f"Dropped solution without a supporting case: {path.description[:60]!r}.")
            continue
        conditions = []
        for condition in _clean(path.conditions):
            if _grounded(condition, corpus):
                conditions.append(condition)
            else:
                notes.append(f"Condition {condition!r} not found in the cases; removed.")
        solutions.append({
            "description": path.description.strip(), "outcome": path.outcome,
            "conditions": conditions, "knowledge_ids": ids,
        })
    environment = []
    for item in _clean(raw.known_environment):
        if _grounded(item, corpus):
            environment.append(item)
        else:
            notes.append(f"Environment detail {item!r} not found in the cases; removed.")
    return ValidSummary(
        title=raw.title.strip()[:500] or "Related cases",
        shared_problem=raw.shared_problem.strip(),
        shared_symptoms=_clean(raw.shared_symptoms),
        known_environment=environment,
        solutions=solutions,
        failed_attempts=_clean(raw.failed_attempts),
        contradictions=_clean(raw.contradictions),
        missing_information=_clean(raw.missing_information),
        notes=notes,
    )
