import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    IncidentSeverity,
    IncidentStatus,
    ResolutionStatus,
)
from app.schemas.common import ORMModel
from app.schemas.threads import MessageRead


class EquipmentRead(ORMModel):
    id: uuid.UUID
    equipment_identifier: str
    equipment_type: str | None
    vendor: str | None
    model: str | None
    site_identifier: str | None


class IncidentRead(ORMModel):
    id: uuid.UUID
    incident_number: str
    title: str
    status: IncidentStatus
    severity: IncidentSeverity | None
    occurred_at: datetime | None
    resolved_at: datetime | None


class EvidenceRead(ORMModel):
    id: uuid.UUID
    # Conversation messages. Troubleshooting feedback is a separate origin
    # (GET /api/knowledge/{id}/feedback) and never appears here as a fake message.
    origin: Literal["conversation"] = "conversation"
    evidence_type: EvidenceType
    explanation: str | None
    message: MessageRead


class KnowledgeItemSummary(ORMModel):
    id: uuid.UUID
    title: str
    problem_description: str
    resolution: str | None
    resolution_status: ResolutionStatus
    approval_status: ApprovalStatus
    created_at: datetime
    updated_at: datetime


class DiscoveryInfo(BaseModel):
    """How the item was discovered. `model_confidence` is the AI's self-assessment, not
    verification; `validation_flags` lists what the server corrected or rejected."""

    thread_id: uuid.UUID
    classification: str
    detection_status: str
    model_name: str | None
    model_confidence: float | None
    analyzed_at: datetime | None
    missing_information: list[str]
    validation_flags: list[str]


class KnowledgeItemDetail(KnowledgeItemSummary):
    candidate_id: uuid.UUID | None
    discovery: DiscoveryInfo | None = None
    symptoms: list[Any]
    root_cause: str | None
    attempted_actions: list[Any]
    applicability_conditions: list[Any]
    evidence: list[EvidenceRead]
    equipment: list[EquipmentRead]
    incidents: list[IncidentRead]
