"""Server-side checks on Gemini output before anything is persisted.

The model's confidence is not verification. These rules make sure every stored
claim points at real messages in the analyzed thread and that "confirmed"
outcomes are backed by a confirming message.
"""

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.ai.analysis_schema import ThreadAnalysis
from app.models.enums import DetectionStatus, EvidenceType, ResolutionStatus

# Classifications that can become a reusable knowledge item.
KNOWLEDGE_CLASSIFICATIONS = frozenset(
    {"unverified_suggestion", "confirmed_resolution", "workaround_or_exception", "access_information"}
)

UNSUPPORTED_CONFIRMATION_NOTE = (
    "No message confirms that the fix worked; stored as a suggestion."
)


@dataclass
class ValidatedEvidence:
    message_id: uuid.UUID
    evidence_type: EvidenceType
    explanation: str


@dataclass
class ValidatedAnalysis:
    classification: str
    is_valuable: bool
    title: str | None
    problem_description: str | None
    symptoms: list[str]
    root_cause: str | None
    equipment_identifiers: list[str]
    incident_numbers: list[str]
    attempted_actions: list[dict[str, Any]]
    resolution: str | None
    resolution_status: ResolutionStatus
    applicability_conditions: list[str]
    missing_information: list[str]
    evidence: list[ValidatedEvidence]
    confidence: float
    rationale: str
    knowledge_type: str = "troubleshooting"
    site_identifiers: list[str] = field(default_factory=list)
    scope: str = "unknown"
    scope_description: str | None = None
    trigger_events: list[str] = field(default_factory=list)
    # Problems found during validation (shown in the UI and stored for auditing).
    flags: list[str] = field(default_factory=list)
    invalid_refs: list[str] = field(default_factory=list)
    rejected_identifiers: list[str] = field(default_factory=list)

    @property
    def creates_knowledge_item(self) -> bool:
        return (
            self.is_valuable
            and self.classification in KNOWLEDGE_CLASSIFICATIONS
            and bool(self.evidence)
            and (self.resolution is not None or bool(self.attempted_actions)
                 or bool(self.applicability_conditions))
        )

    @property
    def detection_status(self) -> DetectionStatus:
        if not self.is_valuable:
            return DetectionStatus.REJECTED
        if self.creates_knowledge_item:
            return DetectionStatus.ACCEPTED  # promoted to a knowledge item (not expert approval)
        return DetectionStatus.INCOMPLETE

    def to_json(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "is_valuable": self.is_valuable,
            "title": self.title,
            "problem_description": self.problem_description,
            "symptoms": self.symptoms,
            "root_cause": self.root_cause,
            "equipment_identifiers": self.equipment_identifiers,
            "incident_numbers": self.incident_numbers,
            "attempted_actions": self.attempted_actions,
            "resolution": self.resolution,
            "resolution_status": self.resolution_status.value,
            "applicability_conditions": self.applicability_conditions,
            "missing_information": self.missing_information,
            "evidence": [
                {"message_id": str(e.message_id), "evidence_type": e.evidence_type.value,
                 "explanation": e.explanation}
                for e in self.evidence
            ],
            "confidence": self.confidence,
            "rationale": self.rationale,
            "knowledge_type": self.knowledge_type,
            "site_identifiers": self.site_identifiers,
            "scope": self.scope,
            "scope_description": self.scope_description,
            "trigger_events": self.trigger_events,
        }


def _clean(values: Sequence[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        text = value.strip()
        if text and text.lower() not in {v.lower() for v in seen}:
            seen[text] = None
    return list(seen)


def validate_analysis(
    analysis: ThreadAnalysis, ref_map: Mapping[str, uuid.UUID], thread_text: str
) -> ValidatedAnalysis:
    """Map message labels to IDs, drop unsupported claims and downgrade unproven confirmations.

    `thread_text` is the concatenated text of the analyzed messages; identifiers the model
    reports must literally appear in it.
    """
    flags: list[str] = []
    invalid_refs: list[str] = []
    lowered_text = thread_text.lower()

    def resolve(refs: Sequence[str]) -> list[uuid.UUID]:
        ids = []
        for ref in refs:
            message_id = ref_map.get(ref.strip())
            if message_id is None:
                invalid_refs.append(ref)
            elif message_id not in ids:
                ids.append(message_id)
        return ids

    # Evidence: only labels from this thread, deduplicated per (message, type).
    evidence: list[ValidatedEvidence] = []
    seen_evidence: set[tuple[uuid.UUID, str]] = set()
    for item in analysis.evidence:
        ids = resolve([item.message_ref])
        if not ids:
            continue
        key = (ids[0], item.evidence_type)
        if key not in seen_evidence:
            seen_evidence.add(key)
            evidence.append(ValidatedEvidence(ids[0], EvidenceType(item.evidence_type), item.explanation.strip()))

    actions = []
    for action in analysis.attempted_actions:
        ids = resolve(action.message_refs)
        if not ids:
            flags.append(f"Dropped action without valid evidence: {action.action}")
            continue
        actions.append({"action": action.action.strip(), "outcome": action.outcome,
                        "message_ids": [str(i) for i in ids]})
        for message_id in ids:
            key = (message_id, EvidenceType.ATTEMPTED_FIX.value)
            if key not in seen_evidence and not any(e.message_id == message_id for e in evidence):
                seen_evidence.add(key)
                evidence.append(ValidatedEvidence(message_id, EvidenceType.ATTEMPTED_FIX, action.action.strip()))

    if invalid_refs:
        flags.append(f"Ignored {len(invalid_refs)} reference(s) to messages outside this thread.")

    # Identifiers must be copied from the conversation, never invented.
    rejected: list[str] = []

    def verified(values: Sequence[str]) -> list[str]:
        kept = []
        for value in _clean(values):
            (kept if value.lower() in lowered_text else rejected).append(value)
        return kept

    equipment = verified(analysis.equipment_identifiers)
    incidents = verified(analysis.incident_numbers)
    sites = verified(analysis.site_identifiers)
    if rejected:
        flags.append(f"Ignored identifiers not found in the conversation: {', '.join(rejected)}")

    classification = analysis.classification
    is_valuable = analysis.is_valuable_knowledge and classification != "irrelevant"
    resolution = (analysis.resolution or "").strip() or None
    missing = _clean(analysis.missing_information)

    # A confirmation must be backed by a message that reports the fix worked.
    status = ResolutionStatus(analysis.resolution_status)
    has_confirmation = any(e.evidence_type is EvidenceType.CONFIRMED_RESOLUTION for e in evidence)
    if status is ResolutionStatus.CONFIRMED_IN_CONVERSATION and not has_confirmation:
        status = ResolutionStatus.SUGGESTED if (resolution or actions) else ResolutionStatus.UNKNOWN
        flags.append(UNSUPPORTED_CONFIRMATION_NOTE)
        missing.append("Confirmation that the fix worked")
        for action in actions:
            if action["outcome"] in ("successful", "partially_successful"):
                action["outcome"] = "unknown"
        if classification == "confirmed_resolution":
            classification = "unverified_suggestion"
    if status is ResolutionStatus.SUGGESTED and not (resolution or actions):
        status = ResolutionStatus.UNKNOWN

    if is_valuable and not evidence:
        flags.append("No valid supporting messages; not stored as a knowledge item.")

    # Events must be grounded in the conversation (every word's stem appears in it).
    events = []
    for event in _clean(analysis.trigger_events):
        words = [w for w in re.findall(r"[a-z0-9]+", event.lower()) if len(w) >= 3]
        if words and all(w[:4] in lowered_text for w in words):
            events.append(event[:200])
        else:
            flags.append(f"Ignored event not mentioned in the conversation: {event}")
    # A class-wide scope needs a concrete device to take the class from.
    scope = analysis.scope if (analysis.scope != "same_equipment_class" or equipment) else "unknown"
    knowledge_type = "site_access" if (analysis.knowledge_type == "site_access"
                                       or classification == "access_information") else "troubleshooting"

    return ValidatedAnalysis(
        classification=classification,
        is_valuable=is_valuable,
        title=(analysis.title or "").strip() or None,
        problem_description=(analysis.problem_description or "").strip() or None,
        symptoms=_clean(analysis.symptoms),
        root_cause=(analysis.root_cause or "").strip() or None,
        equipment_identifiers=equipment,
        incident_numbers=incidents,
        attempted_actions=actions,
        resolution=resolution,
        resolution_status=status,
        applicability_conditions=_clean(analysis.applicability_conditions),
        missing_information=missing,
        evidence=evidence,
        confidence=min(1.0, max(0.0, analysis.confidence)),
        rationale=analysis.rationale.strip(),
        flags=flags,
        invalid_refs=invalid_refs,
        rejected_identifiers=rejected,
        knowledge_type=knowledge_type,
        site_identifiers=sites,
        scope=scope,
        scope_description=(analysis.scope_description or "").strip()[:300] or None,
        trigger_events=events,
    )
