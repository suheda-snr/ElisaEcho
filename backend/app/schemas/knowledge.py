import uuid
from datetime import datetime
from typing import Any

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


class KnowledgeItemDetail(KnowledgeItemSummary):
    candidate_id: uuid.UUID | None
    symptoms: list[Any]
    root_cause: str | None
    attempted_actions: list[Any]
    applicability_conditions: list[Any]
    evidence: list[EvidenceRead]
    equipment: list[EquipmentRead]
    incidents: list[IncidentRead]
