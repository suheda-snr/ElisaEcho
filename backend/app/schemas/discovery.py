import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import (
    ApprovalStatus,
    DetectionStatus,
    ResolutionStatus,
    ThreadProcessingStatus,
)


class DiscoveryMetrics(BaseModel):
    messages_processed: int
    threads_total: int
    threads_analyzed: int
    threads_pending: int
    threads_failed: int
    candidates_detected: int
    conversations_ignored: int
    knowledge_items: int
    confirmed_resolutions: int
    unverified_suggestions: int


class SimulationStatus(BaseModel):
    running: bool
    started_at: datetime | None
    finished_at: datetime | None
    delivered: int
    skipped_duplicates: int
    total: int
    message_interval_seconds: float
    last_error: str | None


class AnalysisQueueStatus(BaseModel):
    gemini_configured: bool
    model: str
    queued: int
    analyzing: int
    debounce_seconds: float
    # Set while Gemini calls are paused because the quota is exhausted.
    paused_until: datetime | None = None
    pause_reason: str | None = None


class DiscoveryStatus(BaseModel):
    simulation: SimulationStatus
    analysis: AnalysisQueueStatus
    metrics: DiscoveryMetrics | None
    # Set when metrics could not be read (e.g. database unavailable).
    metrics_error: str | None = None
    development_controls: bool


class DiscoveryEventRead(BaseModel):
    id: int
    at: datetime
    kind: str
    level: Literal["info", "success", "warning", "error"]
    message: str
    thread_id: uuid.UUID | None
    thread_title: str | None


class CandidateSummary(BaseModel):
    id: uuid.UUID
    classification: str
    detection_status: DetectionStatus
    title: str
    summary: str | None
    confidence: float | None
    model_name: str | None
    analyzed_at: datetime | None
    analyzed_message_count: int
    flags: list[str]
    knowledge_item_id: uuid.UUID | None
    resolution_status: ResolutionStatus | None
    approval_status: ApprovalStatus | None


class ThreadDiscovery(BaseModel):
    id: uuid.UUID
    title: str | None
    external_thread_id: str
    processing_status: ThreadProcessingStatus
    message_count: int
    last_message_at: datetime | None
    candidate: CandidateSummary | None


class AnalysisResult(BaseModel):
    thread_id: uuid.UUID
    status: Literal["analyzed", "unchanged", "empty", "failed", "not_configured", "deferred"]
    classification: str | None
    detection_status: str | None
    candidate_id: uuid.UUID | None
    knowledge_item_id: uuid.UUID | None
    resolution_status: str | None
    confidence: float | None
    flags: list[str]
    error: str | None
    retry_after_seconds: float | None = None


class SimulationCommandResult(BaseModel):
    changed: bool
    simulation: SimulationStatus


class ResetResult(BaseModel):
    guides: int = 0
    threads: int
    messages: int
    candidates: int
    knowledge_items: int
