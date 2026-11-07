import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import ApprovalStatus, EvidenceType, ResolutionStatus, SourceType
from app.schemas.consolidation import GroupBrief
from app.schemas.feedback import FeedbackSummary

OptionalIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None


class SearchFiltersIn(BaseModel):
    equipment_identifier: OptionalIdentifier = None
    incident_number: OptionalIdentifier = None
    approval_status: ApprovalStatus | None = None
    resolution_status: ResolutionStatus | None = None


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    limit: int = Field(default=5, ge=1, le=20)
    filters: SearchFiltersIn = Field(default_factory=SearchFiltersIn)


class EvidenceReference(BaseModel):
    """An original message supporting the knowledge. `excerpt` is the stored message text
    (shortened if long); it is untrusted conversation content, shown as data only."""

    message_id: uuid.UUID
    evidence_type: EvidenceType
    explanation: str | None
    author: str
    sent_at: datetime
    excerpt: str | None
    deleted_at_source: bool
    source_name: str | None
    source_type: SourceType | None
    thread_id: uuid.UUID
    thread_title: str | None
    source_url: str | None


class Ranking(BaseModel):
    """Why this result ranked where it did. Retriever scores are reported as-is and are
    not comparable with each other; `score` is the Reciprocal Rank Fusion total."""

    score: float
    matched_by: list[Literal["semantic", "keyword", "identifier"]]
    semantic_rank: int | None
    semantic_similarity: float | None
    keyword_rank: int | None
    keyword_score: float | None
    identifier_rank: int | None
    matched_identifiers: list[str]


class SearchResult(BaseModel):
    id: uuid.UUID
    title: str
    problem_description: str
    symptoms: list[str]
    root_cause: str | None
    resolution: str | None
    resolution_status: ResolutionStatus
    approval_status: ApprovalStatus
    attempted_actions: list[dict[str, Any]]
    applicability_conditions: list[str]
    missing_information: list[str]
    equipment_identifiers: list[str]
    incident_numbers: list[str]
    evidence_status: Literal["supported", "missing"]
    evidence: list[EvidenceReference]
    ranking: Ranking
    updated_at: datetime
    # The knowledge group this item belongs to (AI-suggested, unreviewed), if any.
    group_id: uuid.UUID | None = None
    # Engineers' troubleshooting feedback (self-reported). Shown only; never used for ranking.
    feedback: FeedbackSummary | None = None


class RetrievalInfo(BaseModel):
    semantic: Literal["used", "no_embeddings", "unavailable", "not_configured"]
    semantic_detail: str | None
    keyword: Literal["used"] = "used"
    identifiers: list[str]
    embedding_model: str | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    retrieval: RetrievalInfo
    # Groups of related incidents behind the results; individual results are still listed.
    related_groups: list[GroupBrief] = []
    # The demo has no per-user authorization; only the source "enabled" flag is enforced.
    access_note: str = "Demo: synthetic data only. Per-user source permissions are not implemented."
