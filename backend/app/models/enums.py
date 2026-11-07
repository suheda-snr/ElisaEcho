"""Allowed values for status-like columns (stored as VARCHAR + CHECK)."""

from enum import StrEnum


class SourceType(StrEnum):
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"
    SIMULATED = "simulated"


class KnowledgeType(StrEnum):
    """What kind of operational context a knowledge item captures."""

    TROUBLESHOOTING = "troubleshooting"  # symptoms -> diagnosis -> action
    SITE_ACCESS = "site_access"  # how to physically reach a site (keys, gates, contacts)


class ThreadProcessingStatus(StrEnum):
    """Where a thread is in the (Phase 3) knowledge-discovery pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class DetectionStatus(StrEnum):
    DETECTED = "detected"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class ResolutionStatus(StrEnum):
    """How well the fix is supported by the conversation itself."""

    UNKNOWN = "unknown"
    SUGGESTED = "suggested"
    CONFIRMED_IN_CONVERSATION = "confirmed_in_conversation"


class ApprovalStatus(StrEnum):
    """Expert review. Independent of ResolutionStatus: a fix confirmed in chat is
    still `unreviewed` until an expert approves it as an operational procedure."""

    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvidenceType(StrEnum):
    PROBLEM_REPORT = "problem_report"
    ATTEMPTED_FIX = "attempted_fix"
    SUGGESTED_SOLUTION = "suggested_solution"
    CONFIRMED_RESOLUTION = "confirmed_resolution"
    APPLICABILITY_CONDITION = "applicability_condition"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GuideStatus(StrEnum):
    READY = "ready"
    # Retrieval found too little evidence; no steps were generated (nothing invented).
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class GuideNodeType(StrEnum):
    START = "start"
    QUESTION = "question"
    DIAGNOSTIC = "diagnostic"
    RECOMMENDATION = "recommendation"
    RESOLUTION = "resolution"
    ESCALATION = "escalation"


class SupportLevel(StrEnum):
    """How strongly a guide step is backed by evidence (derived server-side)."""

    APPROVED = "approved"  # every source knowledge item was approved by an expert
    CONFIRMED_IN_CONVERSATION = "confirmed_in_conversation"
    SUGGESTED = "suggested"
    CONFLICTING = "conflicting"
    NONE = "none"  # navigation step without evidence (start, question, escalation)


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class SessionStepType(StrEnum):
    ANSWER = "answer"
    OBSERVATION = "observation"
    BACK = "back"
    COMPLETE = "complete"
