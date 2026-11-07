"""Troubleshooting feedback (Phase 6C): requests, records and per-knowledge summaries.

Feedback is self-reported by the engineer. Clients can never set `verification_status`
(requests forbid unknown fields), and feedback never changes a knowledge item's resolution
or approval status.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Outcome = Literal["resolved", "not_resolved", "partially_resolved", "unknown", "not_attempted"]
AttemptOutcome = Literal["resolved", "not_resolved", "partially_resolved", "unknown"]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class _FeedbackFields(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. a client-supplied verification_status is rejected

    attempted: bool
    # Required when attempted; must be omitted (or "not_attempted") when not attempted.
    outcome: Outcome | None = None
    equipment_identifier: Short | None = None
    firmware_version: Short | None = None
    environment_details: dict[str, Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] | None = None
    engineer_notes: Notes | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if not self.attempted:
            if self.outcome not in (None, "not_attempted"):
                raise ValueError("A recommendation that was not attempted cannot have an outcome.")
            self.outcome = "not_attempted"
        elif self.outcome in (None, "not_attempted"):
            raise ValueError("Choose the result of the attempt (resolved, not resolved, partially resolved or unknown).")
        for name in ("equipment_identifier", "firmware_version", "engineer_notes"):
            if getattr(self, name) == "":
                setattr(self, name, None)
        if self.environment_details is not None:
            self.environment_details = {k.strip()[:60]: v for k, v in self.environment_details.items()
                                        if k.strip() and v} or None
        return self


class FeedbackCreate(_FeedbackFields):
    troubleshooting_session_id: uuid.UUID
    guide_node_id: uuid.UUID
    knowledge_item_id: uuid.UUID


class FeedbackUpdate(_FeedbackFields):
    pass


class FeedbackRead(BaseModel):
    id: uuid.UUID
    origin: Literal["troubleshooting_feedback"] = "troubleshooting_feedback"
    troubleshooting_session_id: uuid.UUID
    guide_node_id: uuid.UUID
    recommendation: str  # title of the guide step that was evaluated
    knowledge_item_id: uuid.UUID
    knowledge_title: str
    attempted: bool
    outcome: Outcome
    equipment_identifier: str | None
    firmware_version: str | None
    environment_details: dict[str, Any] | None
    engineer_notes: str | None
    verification_status: Literal["self_reported", "independently_verified"]
    # Deterministic comparison with the original conversation evidence.
    relation_to_original: Literal["supports", "contradicts", "mixed", "new_evidence", "no_attempt", "inconclusive"]
    submitted_at: datetime
    updated_at: datetime
    revision: int


class FeedbackSaved(FeedbackRead):
    created: bool
    # Returned once, on creation only: send it as X-Feedback-Token to correct this feedback.
    edit_token: str | None = None


class OutcomeCounts(BaseModel):
    resolved: int = 0
    not_resolved: int = 0
    partially_resolved: int = 0
    unknown: int = 0
    not_attempted: int = 0

    @property
    def attempts(self) -> int:
        return self.resolved + self.not_resolved + self.partially_resolved + self.unknown


class ConditionBreakdown(BaseModel):
    value: str | None  # None = not reported
    counts: OutcomeCounts


class FeedbackSummary(BaseModel):
    knowledge_item_id: uuid.UUID
    sessions: int  # distinct troubleshooting sessions with feedback on this knowledge
    attempts: int
    counts: OutcomeCounts
    independently_verified: int
    has_conflicting_reports: bool  # both resolved and not-resolved reports exist
    # Only when attempts >= min_sample_for_rate; self-reported, not a measured probability.
    success_rate: float | None
    min_sample_for_rate: int
    by_firmware: list[ConditionBreakdown]
    by_equipment: list[ConditionBreakdown]
    condition_notes: list[str]  # e.g. "Not resolved on firmware 4.0 (1 report)"
    last_reported_at: datetime | None
    note: str = ("Self-reported by engineers after guided troubleshooting. Not independently verified and "
                 "not an approval; the knowledge's own status is unchanged.")
