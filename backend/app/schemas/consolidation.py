"""Responses for related knowledge and knowledge groups (Phase 6B).

Groups and relationships are AI-derived suggestions over unmodified knowledge items. Group
summaries are never approved knowledge (`review_status` is always "unreviewed").
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import ApprovalStatus, ResolutionStatus


class CaseRef(BaseModel):
    id: uuid.UUID
    title: str
    resolution_status: ResolutionStatus
    approval_status: ApprovalStatus
    conversation: str | None
    source_name: str | None
    thread_id: uuid.UUID | None


class EvidenceRef(BaseModel):
    message_id: uuid.UUID
    author: str
    sent_at: datetime
    excerpt: str
    source_url: str | None


class ConditionRead(BaseModel):
    field: str
    source_value: str | None  # None = not stated in that conversation (unknown, not "same")
    target_value: str | None


class RelationshipRead(BaseModel):
    id: uuid.UUID
    relationship_type: str
    outcome_comparison: str | None
    explanation: str | None
    source: CaseRef
    target: CaseRef
    shared_symptoms: list[str]
    shared_equipment: list[str]
    conditions: list[ConditionRead]
    unknown_conditions: list[str]
    source_evidence: list[EvidenceRef]
    target_evidence: list[EvidenceRef]
    validation_notes: list[str]
    model_name: str | None
    updated_at: datetime


class GroupBrief(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None
    case_count: int
    independent_conversations: int
    solution_count: int
    successful_paths: int
    conflict_count: int
    summary_pending: bool  # no summary yet, or members changed since it was generated
    review_status: str = "unreviewed"
    updated_at: datetime


class SolutionRead(BaseModel):
    description: str
    outcome: str
    conditions: list[str]
    knowledge_ids: list[uuid.UUID]


class GroupMemberRead(CaseRef):
    problem_description: str
    resolution: str | None
    equipment: list[str]
    applicability_conditions: list[Any]
    evidence_count: int


class GroupDetail(GroupBrief):
    shared_problem: str | None
    shared_symptoms: list[str]
    known_environment: list[str]
    solutions: list[SolutionRead]
    failed_attempts: list[str]
    contradictions: list[str]
    missing_information: list[str]
    summary_model: str | None
    generated_at: str | None
    members: list[GroupMemberRead]


class RelatedKnowledge(BaseModel):
    knowledge_id: uuid.UUID
    group: GroupBrief | None
    relationships: list[RelationshipRead]  # strongest first; "unrelated" pairs are omitted
