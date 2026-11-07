import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    GuideNodeType,
    GuideStatus,
    ResolutionStatus,
    SessionStatus,
    SessionStepType,
    SourceType,
    SupportLevel,
)

Text500 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Text2000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class GenerateGuideRequest(BaseModel):
    problem: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]
    equipment_identifier: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None


class NodeEvidenceRead(BaseModel):
    message_id: uuid.UUID
    knowledge_item_id: uuid.UUID
    evidence_type: EvidenceType
    author: str
    sent_at: datetime
    excerpt: str | None
    deleted_at_source: bool
    source_name: str | None
    source_type: SourceType | None
    thread_title: str | None
    source_url: str | None


class GuideNodeRead(BaseModel):
    id: uuid.UUID
    key: str
    node_type: GuideNodeType
    title: str
    description: str | None
    question: str | None
    expected_answers: list[str]
    applicability_conditions: list[str]
    knowledge_item_ids: list[uuid.UUID]
    approval_status: ApprovalStatus | None
    support_level: SupportLevel
    requires_manual_verification: bool
    conflict_note: str | None
    evidence: list[NodeEvidenceRead]


class GuideEdgeRead(BaseModel):
    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    answer_label: str
    condition: str | None


class KnowledgeRef(BaseModel):
    id: uuid.UUID
    title: str
    problem_description: str
    resolution: str | None
    resolution_status: ResolutionStatus
    approval_status: ApprovalStatus
    applicability_conditions: list[str]
    missing_information: list[str]
    equipment_identifiers: list[str]
    incident_numbers: list[str]
    conversation: str | None
    source_name: str | None


class GuideRead(BaseModel):
    id: uuid.UUID
    title: str
    problem_description: str
    equipment_identifier: str | None
    status: GuideStatus
    status_reason: str | None
    summary: str | None
    model_name: str | None
    created_at: datetime
    start_node_id: uuid.UUID | None
    nodes: list[GuideNodeRead]
    edges: list[GuideEdgeRead]
    knowledge: list[KnowledgeRef]
    conflicts: list[str]
    uncertainties: list[str]
    validation_notes: list[str]
    safety_notice: str = (
        "Decision support only. Elisa Echo does not run commands or change configurations. "
        "Steps based on unapproved knowledge must follow your organization's authorization "
        "and change-management procedures."
    )


class GuideSummary(BaseModel):
    id: uuid.UUID
    title: str
    problem_description: str
    status: GuideStatus
    created_at: datetime


# ---- sessions ----------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    guide_id: uuid.UUID


class StepRequest(BaseModel):
    """`answer`: choose an answer at the current step. `observation`: add a note (and
    optionally an action taken) at the current step. `back`: return to an earlier step on the
    active path (default: the previous one); later answers are kept as superseded history."""

    type: Literal["answer", "observation", "back"]
    answer_label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    observation: Text2000 | None = None
    action_taken: Text500 | None = None
    to_node_id: uuid.UUID | None = None


class CompleteSessionRequest(BaseModel):
    outcome: Literal["resolved", "unresolved"]
    summary: Text2000
    action_taken: Text500 | None = None
    observation: Text2000 | None = None


class SessionStepRead(BaseModel):
    id: uuid.UUID
    sequence: int
    step_type: SessionStepType
    node_id: uuid.UUID | None
    answer_label: str | None
    target_node_id: uuid.UUID | None
    observation: str | None
    action_taken: str | None
    superseded: bool
    created_at: datetime


class SessionRead(BaseModel):
    id: uuid.UUID
    guide_id: uuid.UUID
    status: SessionStatus
    current_node_id: uuid.UUID | None
    active_path: list[uuid.UUID]
    outcome_summary: str | None
    action_taken: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    steps: list[SessionStepRead]
    note: str = "Session outcomes are the engineer's report. They are not promoted to approved knowledge."


class SessionDetail(SessionRead):
    guide: GuideRead


class SessionSummary(BaseModel):
    id: uuid.UUID
    guide_id: uuid.UUID
    guide_title: str
    problem_description: str
    status: SessionStatus
    updated_at: datetime
