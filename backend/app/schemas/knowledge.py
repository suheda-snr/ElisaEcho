import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    IncidentSeverity,
    IncidentStatus,
    KnowledgeType,
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


class EntityLinkRead(ORMModel):
    entity_type: str  # equipment | unit_class | site | event
    label: str
    relation: str  # observed_on | applies_to | located_at | access_to | triggered_by
    source: str  # conversation | inventory


class SupersededByRef(BaseModel):
    id: uuid.UUID
    title: str


class ContextFields(BaseModel):
    """Context-assertion fields shared by knowledge reads and search results."""

    knowledge_type: KnowledgeType = KnowledgeType.TROUBLESHOOTING
    valid_from: datetime | None = None
    valid_to: datetime | None = None  # None = still believed true
    validity_note: str | None = None
    superseded_by: SupersededByRef | None = None
    entity_links: list[EntityLinkRead] = []

    @property
    def is_current(self) -> bool:
        return self.valid_to is None or self.valid_to > datetime.now(UTC)


class KnowledgeItemSummary(ORMModel):
    id: uuid.UUID
    title: str
    problem_description: str
    resolution: str | None
    resolution_status: ResolutionStatus
    approval_status: ApprovalStatus
    knowledge_type: KnowledgeType = KnowledgeType.TROUBLESHOOTING
    valid_to: datetime | None = None
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


class KnowledgeItemDetail(ContextFields, KnowledgeItemSummary):
    candidate_id: uuid.UUID | None
    discovery: DiscoveryInfo | None = None
    symptoms: list[Any]
    root_cause: str | None
    attempted_actions: list[Any]
    applicability_conditions: list[Any]
    evidence: list[EvidenceRead]
    equipment: list[EquipmentRead]
    incidents: list[IncidentRead]
