"""Record and correct engineers' feedback on troubleshooting recommendations.

Validation (all server-side):
- the session exists and the step belongs to that session's guide;
- the step is a recommendation or resolution, and the engineer actually reached it;
- the knowledge item is one the step was built from (no feedback on unrelated knowledge);
- attempted/outcome are consistent (schema).

Idempotency: one row per (session, step, knowledge item). Re-sending identical feedback
returns the existing row; different feedback for the same recommendation must be a
correction with the edit token, which keeps the previous version in `revisions`.
There are no user accounts: the edit token returned at creation is the only way to modify
feedback (a demo-level safeguard, not authentication).
"""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuideNode, KnowledgeItem, TroubleshootingFeedback, TroubleshootingSession
from app.models.enums import GuideNodeType, ResolutionStatus
from app.schemas.feedback import FeedbackCreate, FeedbackRead, FeedbackUpdate
from app.services.guides.read import load_guide, load_session

FEEDBACK_NODE_TYPES = (GuideNodeType.RECOMMENDATION, GuideNodeType.RESOLUTION)
_FIELDS = ("attempted", "outcome", "equipment_identifier", "firmware_version", "environment_details",
           "engineer_notes")


class FeedbackError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass
class SaveResult:
    feedback: TroubleshootingFeedback
    created: bool
    edit_token: str | None = None


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(row: TroubleshootingFeedback, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(row.edit_token_hash, _hash(token))


def _values(source: Any) -> dict[str, Any]:
    return {name: getattr(source, name) for name in _FIELDS}


async def _validate(db: AsyncSession, body: FeedbackCreate) -> None:
    ts = await load_session(db, body.troubleshooting_session_id)
    if ts is None:
        raise FeedbackError(404, "Troubleshooting session not found.")
    guide = await load_guide(db, ts.guide_id)
    node = next((n for n in guide.nodes if n.id == body.guide_node_id), None) if guide else None
    if node is None:
        raise FeedbackError(422, "This step is not part of the session's troubleshooting guide.")
    if node.node_type not in FEEDBACK_NODE_TYPES:
        raise FeedbackError(422, "Feedback can only be given on recommendation or resolution steps.")
    if str(body.knowledge_item_id) not in {str(k) for k in node.knowledge_item_ids}:
        raise FeedbackError(422, "This knowledge item is not a source of the selected recommendation.")
    if await db.get(KnowledgeItem, body.knowledge_item_id) is None:
        raise FeedbackError(404, "Knowledge item not found (it may have been removed).")
    reached = {ts.current_node_id} | {s.node_id for s in ts.steps} | {s.target_node_id for s in ts.steps}
    if node.id not in reached:
        raise FeedbackError(409, "Reach this step in the session before reporting on it.")


async def _existing(db: AsyncSession, body: FeedbackCreate) -> TroubleshootingFeedback | None:
    return await db.scalar(select(TroubleshootingFeedback).where(
        TroubleshootingFeedback.troubleshooting_session_id == body.troubleshooting_session_id,
        TroubleshootingFeedback.guide_node_id == body.guide_node_id,
        TroubleshootingFeedback.knowledge_item_id == body.knowledge_item_id,
    ))


def _apply(row: TroubleshootingFeedback, body: FeedbackUpdate | FeedbackCreate) -> None:
    previous = _values(row)
    previous["revision"] = row.revision
    previous["replaced_at"] = datetime.now(UTC).isoformat()
    row.revisions = [*(row.revisions or []), previous]
    for name, value in _values(body).items():
        setattr(row, name, value)
    row.revision += 1
    row.updated_at = datetime.now(UTC)


async def submit_feedback(db: AsyncSession, body: FeedbackCreate, token: str | None = None) -> SaveResult:
    await _validate(db, body)
    existing = await _existing(db, body)
    if existing is not None:
        return await _resubmit(db, existing, body, token)

    edit_token = secrets.token_urlsafe(24)
    row = TroubleshootingFeedback(
        troubleshooting_session_id=body.troubleshooting_session_id, guide_node_id=body.guide_node_id,
        knowledge_item_id=body.knowledge_item_id, verification_status="self_reported",
        edit_token_hash=_hash(edit_token), revision=1, revisions=[], **_values(body),
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:  # a concurrent duplicate submission won the race
        await db.rollback()
        existing = await _existing(db, body)
        if existing is None:
            raise
        return await _resubmit(db, existing, body, token)
    return SaveResult(row, created=True, edit_token=edit_token)


async def _resubmit(db: AsyncSession, row: TroubleshootingFeedback, body: FeedbackCreate,
                    token: str | None) -> SaveResult:
    if _values(row) == _values(body):
        return SaveResult(row, created=False)  # duplicate submission: nothing new
    if not token_matches(row, token):
        raise FeedbackError(409, "Feedback for this recommendation was already submitted in this session. "
                                 "Correct it instead (requires the edit token from the original submission).")
    _apply(row, body)
    await db.commit()
    return SaveResult(row, created=False)


async def update_feedback(db: AsyncSession, feedback_id: uuid.UUID, body: FeedbackUpdate,
                          token: str | None) -> TroubleshootingFeedback:
    row = await db.scalar(select(TroubleshootingFeedback).where(TroubleshootingFeedback.id == feedback_id)
                          .with_for_update())
    if row is None:
        raise FeedbackError(404, "Feedback not found.")
    if not token_matches(row, token):
        raise FeedbackError(403, "Only the engineer who submitted this feedback can correct it "
                                 "(missing or invalid X-Feedback-Token).")
    if _values(row) != _values(body):
        _apply(row, body)
    await db.commit()
    return row


# ---- reads ---------------------------------------------------------------------------------


def relation_to_original(outcome: str, resolution: ResolutionStatus) -> str:
    if outcome == "not_attempted":
        return "no_attempt"
    if outcome == "unknown":
        return "inconclusive"
    if outcome == "partially_resolved":
        return "mixed"
    if outcome == "not_resolved":
        return "contradicts"
    return "supports" if resolution is ResolutionStatus.CONFIRMED_IN_CONVERSATION else "new_evidence"


async def feedback_reads(db: AsyncSession, rows: list[TroubleshootingFeedback]) -> list[FeedbackRead]:
    if not rows:
        return []
    nodes = dict((await db.execute(select(GuideNode.id, GuideNode.title).where(
        GuideNode.id.in_({r.guide_node_id for r in rows})))).all())
    items = {k.id: k for k in await db.scalars(select(KnowledgeItem).where(
        KnowledgeItem.id.in_({r.knowledge_item_id for r in rows})))}
    out = []
    for r in rows:
        item = items.get(r.knowledge_item_id)
        out.append(FeedbackRead(
            id=r.id, troubleshooting_session_id=r.troubleshooting_session_id, guide_node_id=r.guide_node_id,
            recommendation=nodes.get(r.guide_node_id, "Recommendation"), knowledge_item_id=r.knowledge_item_id,
            knowledge_title=item.title if item else "Removed knowledge", attempted=r.attempted, outcome=r.outcome,
            equipment_identifier=r.equipment_identifier, firmware_version=r.firmware_version,
            environment_details=r.environment_details, engineer_notes=r.engineer_notes,
            verification_status=r.verification_status,
            relation_to_original=relation_to_original(
                r.outcome, item.resolution_status if item else ResolutionStatus.UNKNOWN),
            submitted_at=r.submitted_at, updated_at=r.updated_at, revision=r.revision,
        ))
    return out


async def session_feedback(db: AsyncSession, session_id: uuid.UUID) -> list[FeedbackRead] | None:
    if await db.get(TroubleshootingSession, session_id) is None:
        return None
    rows = list(await db.scalars(select(TroubleshootingFeedback).where(
        TroubleshootingFeedback.troubleshooting_session_id == session_id
    ).order_by(TroubleshootingFeedback.submitted_at)))
    return await feedback_reads(db, rows)


async def knowledge_feedback(db: AsyncSession, knowledge_id: uuid.UUID, *, limit: int, offset: int
                             ) -> tuple[list[FeedbackRead], int]:
    query = select(TroubleshootingFeedback).where(TroubleshootingFeedback.knowledge_item_id == knowledge_id)
    rows = list(await db.scalars(query.order_by(TroubleshootingFeedback.updated_at.desc())))
    return await feedback_reads(db, rows[offset: offset + limit]), len(rows)
