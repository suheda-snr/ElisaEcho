"""Analyze one conversation thread and persist what was discovered.

Idempotency and incremental updates:
- Each thread has at most one knowledge candidate (and so one knowledge item). Re-analysis
  updates them in place; it never creates a second item for the same thread.
- A fingerprint of the analyzed messages is stored on the candidate. If nothing changed
  since the last successful analysis, Gemini is not called again.
- The final write happens under a row lock on the thread (SELECT ... FOR UPDATE).

Approval status is never changed here: confirmation in chat is not expert approval.
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.analysis_schema import ThreadAnalysis
from app.ai.gemini import (
    GeminiClient,
    GeminiError,
    GeminiNotConfiguredError,
    GeminiQuotaExceededError,
)
from app.models import (
    ConversationThread,
    Equipment,
    Incident,
    KnowledgeCandidate,
    KnowledgeEvidence,
    KnowledgeItem,
    Message,
)
from app.models.enums import ResolutionStatus, ThreadProcessingStatus
from app.services.discovery.prompt import SYSTEM_INSTRUCTION, build_prompt
from app.services.discovery.validation import ValidatedAnalysis, validate_analysis

logger = logging.getLogger(__name__)

OutcomeStatus = Literal["analyzed", "unchanged", "empty", "failed", "not_configured", "deferred"]


class ThreadNotFoundError(LookupError):
    pass


@dataclass
class AnalysisOutcome:
    thread_id: uuid.UUID
    status: OutcomeStatus
    classification: str | None = None
    detection_status: str | None = None
    candidate_id: uuid.UUID | None = None
    knowledge_item_id: uuid.UUID | None = None
    resolution_status: str | None = None
    confidence: float | None = None
    flags: list[str] = field(default_factory=list)
    error: str | None = None
    # Set when Gemini asked us to wait (quota/rate limit).
    retry_after_seconds: float | None = None


def fingerprint_messages(messages: list[Message]) -> str:
    """Stable hash of everything that affects analysis (content, edits, deletions)."""
    payload = [
        [m.external_message_id, m.content, m.edited_at and m.edited_at.isoformat(),
         m.deleted_at and m.deleted_at.isoformat()]
        for m in messages
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


async def _messages(session: AsyncSession, thread_id: uuid.UUID) -> list[Message]:
    result = await session.scalars(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.sent_at, Message.external_message_id)
        .execution_options(populate_existing=True)
    )
    return list(result)


async def _candidate(session: AsyncSession, thread_id: uuid.UUID) -> KnowledgeCandidate | None:
    return await session.scalar(
        select(KnowledgeCandidate)
        .where(KnowledgeCandidate.thread_id == thread_id)
        .order_by(KnowledgeCandidate.created_at)
        .limit(1)
        .options(
            selectinload(KnowledgeCandidate.knowledge_item).selectinload(KnowledgeItem.evidence),
            selectinload(KnowledgeCandidate.knowledge_item).selectinload(KnowledgeItem.equipment),
            selectinload(KnowledgeCandidate.knowledge_item).selectinload(KnowledgeItem.incidents),
        )
        .execution_options(populate_existing=True)
    )


async def _set_status(session: AsyncSession, thread: ConversationThread, status: ThreadProcessingStatus) -> None:
    thread.processing_status = status
    await session.commit()


async def analyze_thread(
    session: AsyncSession,
    thread_id: uuid.UUID,
    gemini: GeminiClient,
    *,
    force: bool = False,
) -> AnalysisOutcome:
    thread = await session.get(ConversationThread, thread_id, populate_existing=True)
    if thread is None:
        raise ThreadNotFoundError(thread_id)

    messages = await _messages(session, thread_id)
    fingerprint = fingerprint_messages(messages)
    candidate = await _candidate(session, thread_id)

    if not force and candidate is not None and candidate.extracted_data.get("fingerprint") == fingerprint:
        if thread.processing_status is not ThreadProcessingStatus.PROCESSED:
            await _set_status(session, thread, ThreadProcessingStatus.PROCESSED)
        return _outcome(thread_id, "unchanged", candidate, candidate.knowledge_item)

    active = [m for m in messages if m.deleted_at is None]
    if not active:
        await _set_status(session, thread, ThreadProcessingStatus.PROCESSED)
        return AnalysisOutcome(thread_id=thread_id, status="empty")

    if not gemini.configured:
        return AnalysisOutcome(
            thread_id=thread_id, status="not_configured",
            error="Gemini is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    await _set_status(session, thread, ThreadProcessingStatus.PROCESSING)

    prompt = build_prompt(thread.title, active)
    try:
        analysis = await gemini.generate_structured(
            system_instruction=SYSTEM_INSTRUCTION, contents=prompt.contents, schema=ThreadAnalysis
        )
    except GeminiNotConfiguredError as exc:
        await _set_status(session, thread, ThreadProcessingStatus.PENDING)
        return AnalysisOutcome(thread_id=thread_id, status="not_configured", error=str(exc))
    except GeminiError as exc:
        # Never fabricate a result: record the failure and leave existing knowledge untouched.
        logger.warning("Analysis failed for thread %s: %s", thread_id, type(exc).__name__)
        await _set_status(session, thread, ThreadProcessingStatus.FAILED)
        retry_after = exc.retry_after_seconds if isinstance(exc, GeminiQuotaExceededError) else None
        return AnalysisOutcome(
            thread_id=thread_id, status="failed", error=str(exc), retry_after_seconds=retry_after
        )

    thread_text = "\n".join(m.content for m in active)
    validated = validate_analysis(analysis, prompt.ref_map, thread_text)
    return await _persist(session, thread_id, fingerprint, active, validated, analysis, gemini.model)


async def _persist(
    session: AsyncSession,
    thread_id: uuid.UUID,
    fingerprint: str,
    analyzed: list[Message],
    validated: ValidatedAnalysis,
    raw: ThreadAnalysis,
    model_name: str,
) -> AnalysisOutcome:
    # Serialize concurrent writers for this thread.
    thread = await session.scalar(
        select(ConversationThread)
        .where(ConversationThread.id == thread_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert thread is not None
    candidate = await _candidate(session, thread_id)

    if candidate is None:
        candidate = KnowledgeCandidate(thread_id=thread_id, candidate_type=validated.classification, title="")
        session.add(candidate)

    candidate.candidate_type = validated.classification
    candidate.title = (validated.title or thread.title or "Untitled conversation")[:500]
    candidate.summary = validated.problem_description or validated.rationale
    candidate.detection_status = validated.detection_status
    candidate.confidence = validated.confidence
    candidate.model_name = model_name
    candidate.extracted_data = {
        "fingerprint": fingerprint,
        "analyzed_at": datetime.now(UTC).isoformat(),
        "analyzed_message_ids": [str(m.id) for m in analyzed],
        "analysis": validated.to_json(),
        "validation": {
            "flags": validated.flags,
            "invalid_refs": validated.invalid_refs,
            "rejected_identifiers": validated.rejected_identifiers,
        },
        "model_output": raw.model_dump(mode="json"),
    }

    item = candidate.knowledge_item
    if validated.creates_knowledge_item:
        if item is None:
            item = KnowledgeItem(candidate=candidate, title="", problem_description="")
            item.evidence, item.equipment, item.incidents = [], [], []
            session.add(item)
        item.title = candidate.title
        item.problem_description = validated.problem_description or candidate.title
        item.symptoms = validated.symptoms
        item.root_cause = validated.root_cause
        item.resolution = validated.resolution
        item.attempted_actions = validated.attempted_actions
        item.applicability_conditions = validated.applicability_conditions
        item.resolution_status = validated.resolution_status
        # approval_status is intentionally left untouched (defaults to "unreviewed").
        await _sync_evidence(item, validated)
        item.equipment = await _equipment(session, validated.equipment_identifiers)
        item.incidents = await _incidents(session, validated.incident_numbers, item.title)
    elif item is not None:
        # Re-analysis no longer supports the earlier knowledge (e.g. messages were deleted
        # or edited): keep the record for review but drop its evidence and certainty.
        item.resolution_status = ResolutionStatus.UNKNOWN
        item.evidence = []
        validated.flags.append("Earlier knowledge is no longer supported by the conversation.")
        candidate.extracted_data = {**candidate.extracted_data, "validation": {
            **candidate.extracted_data["validation"], "flags": validated.flags}}

    await session.flush()

    # New messages may have arrived while Gemini was thinking: keep the thread pending then.
    current = fingerprint_messages(await _messages(session, thread_id))
    thread.processing_status = (
        ThreadProcessingStatus.PROCESSED if current == fingerprint else ThreadProcessingStatus.PENDING
    )
    outcome = _outcome(thread_id, "analyzed", candidate, item)
    await session.commit()
    return outcome


async def _sync_evidence(item: KnowledgeItem, validated: ValidatedAnalysis) -> None:
    wanted = {(e.message_id, e.evidence_type): e for e in validated.evidence}
    kept = []
    for existing in item.evidence:
        match = wanted.pop((existing.message_id, existing.evidence_type), None)
        if match is not None:
            existing.explanation = match.explanation
            kept.append(existing)
    for e in wanted.values():
        kept.append(KnowledgeEvidence(message_id=e.message_id, evidence_type=e.evidence_type, explanation=e.explanation))
    item.evidence = kept  # removed rows are deleted (delete-orphan); messages are untouched


async def _equipment(session: AsyncSession, identifiers: list[str]) -> list[Equipment]:
    if not identifiers:
        return []
    await session.execute(
        insert(Equipment)
        .values([{"equipment_identifier": i[:100]} for i in identifiers])
        .on_conflict_do_nothing(index_elements=["equipment_identifier"])
    )
    result = await session.scalars(
        select(Equipment).where(Equipment.equipment_identifier.in_([i[:100] for i in identifiers]))
    )
    return list(result)


async def _incidents(session: AsyncSession, numbers: list[str], title: str) -> list[Incident]:
    if not numbers:
        return []
    await session.execute(
        insert(Incident)
        .values([{"incident_number": n[:100], "title": title[:500]} for n in numbers])
        .on_conflict_do_nothing(index_elements=["incident_number"])
    )
    result = await session.scalars(select(Incident).where(Incident.incident_number.in_([n[:100] for n in numbers])))
    return list(result)


def _outcome(
    thread_id: uuid.UUID, status: OutcomeStatus, candidate: KnowledgeCandidate, item: KnowledgeItem | None
) -> AnalysisOutcome:
    validation = candidate.extracted_data.get("validation", {})
    return AnalysisOutcome(
        thread_id=thread_id,
        status=status,
        classification=candidate.candidate_type,
        detection_status=candidate.detection_status.value,
        candidate_id=candidate.id,
        knowledge_item_id=item.id if item is not None else None,
        resolution_status=item.resolution_status.value if item is not None else None,
        confidence=candidate.confidence,
        flags=list(validation.get("flags", [])),
    )
