"""Aggregate troubleshooting feedback per knowledge item.

- One report per (knowledge item, session): if a session gave feedback on several steps of
  the same knowledge, its most recent attempt counts (else its "not attempted" report), so
  one engineer's session is never counted as several independent confirmations.
- Success/failure totals only include actual attempts.
- A success rate is only given from MIN_SAMPLE_FOR_RATE attempts on, and is labelled as
  self-reported. Feedback never changes approval status.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TroubleshootingFeedback
from app.schemas.feedback import ConditionBreakdown, FeedbackSummary, OutcomeCounts

MIN_SAMPLE_FOR_RATE = 5

_LABELS = {"resolved": "resolved", "not_resolved": "not resolved", "partially_resolved": "partially resolved",
           "unknown": "outcome unknown"}


def _representatives(rows: Iterable[TroubleshootingFeedback]) -> list[TroubleshootingFeedback]:
    per_session: dict[uuid.UUID, TroubleshootingFeedback] = {}
    for row in sorted(rows, key=lambda r: r.updated_at):
        current = per_session.get(row.troubleshooting_session_id)
        if current is None or row.attempted or not current.attempted:
            per_session[row.troubleshooting_session_id] = row
    return list(per_session.values())


def _breakdown(rows: list[TroubleshootingFeedback], attr: str) -> list[ConditionBreakdown]:
    groups: dict[str | None, OutcomeCounts] = {}
    display: dict[str | None, str | None] = {}
    for row in rows:
        if not row.attempted:
            continue
        raw = getattr(row, attr)
        key = " ".join(raw.lower().split()) if raw else None
        display.setdefault(key, raw.strip() if raw else None)
        counts = groups.setdefault(key, OutcomeCounts())
        setattr(counts, row.outcome, getattr(counts, row.outcome) + 1)
    ordered = sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))
    return [ConditionBreakdown(value=display[k], counts=c) for k, c in ordered]


def _notes(by_firmware: list[ConditionBreakdown], conflicting: bool) -> list[str]:
    known = [b for b in by_firmware if b.value is not None]
    if not (conflicting or len(known) > 1):
        return []
    notes = []
    for b in by_firmware:
        parts = [f"{_LABELS[k]} {v}" for k, v in b.counts.model_dump().items() if v and k in _LABELS]
        if parts:
            where = f"Firmware {b.value}" if b.value else "Firmware not reported"
            notes.append(f"{where}: {', '.join(parts)}")
    return notes


def summarize(knowledge_id: uuid.UUID, rows: list[TroubleshootingFeedback]) -> FeedbackSummary:
    reps = _representatives(rows)
    counts = OutcomeCounts()
    for row in reps:
        setattr(counts, row.outcome, getattr(counts, row.outcome) + 1)
    attempts = counts.attempts
    conflicting = counts.resolved > 0 and counts.not_resolved > 0
    by_firmware = _breakdown(reps, "firmware_version")
    return FeedbackSummary(
        knowledge_item_id=knowledge_id,
        sessions=len(reps),
        attempts=attempts,
        counts=counts,
        independently_verified=sum(r.attempted and r.verification_status == "independently_verified" for r in reps),
        has_conflicting_reports=conflicting,
        success_rate=round(counts.resolved / attempts, 3) if attempts >= MIN_SAMPLE_FOR_RATE else None,
        min_sample_for_rate=MIN_SAMPLE_FOR_RATE,
        by_firmware=by_firmware,
        by_equipment=_breakdown(reps, "equipment_identifier"),
        condition_notes=_notes(by_firmware, conflicting),
        last_reported_at=max((r.updated_at for r in rows), default=None),
    )


async def feedback_summaries(db: AsyncSession, knowledge_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, FeedbackSummary]:
    """Summaries for the items that have feedback (others are absent)."""
    ids = list(set(knowledge_ids))
    if not ids:
        return {}
    grouped: dict[uuid.UUID, list[TroubleshootingFeedback]] = defaultdict(list)
    for row in await db.scalars(select(TroubleshootingFeedback).where(
            TroubleshootingFeedback.knowledge_item_id.in_(ids))):
        grouped[row.knowledge_item_id].append(row)
    return {kid: summarize(kid, rows) for kid, rows in grouped.items()}


async def feedback_summary(db: AsyncSession, knowledge_id: uuid.UUID) -> FeedbackSummary:
    return (await feedback_summaries(db, [knowledge_id])).get(knowledge_id) or summarize(knowledge_id, [])


def summary_text(s: FeedbackSummary) -> str:
    """One line for prompts and logs, e.g. 'Reported resolved in 1 session; not resolved in 1.'"""
    c = s.counts
    parts = [f"{_LABELS[k]} in {v}" for k, v in c.model_dump().items() if v and k in _LABELS]
    text = ("Reported " + "; ".join(parts) + " troubleshooting session(s)") if parts else "No attempts reported"
    if c.not_attempted:
        text += f"; not attempted in {c.not_attempted}"
    return text + "."
