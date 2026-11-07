"""Engineers' troubleshooting sessions: navigate a guide, record answers and observations.

Steps are append-only. Going back marks later answers as superseded (they stay in the
history) and moves the current step, so the active path is always consistent.
Session outcomes are the engineer's own report and are never promoted to knowledge.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuideEdge, SessionStep, TroubleshootingSession
from app.models.enums import GuideNodeType, GuideStatus, SessionStatus, SessionStepType
from app.schemas.guides import CompleteSessionRequest, StepRequest
from app.services.guides.read import active_path, load_guide, load_session, start_node


class SessionError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def create_session(db: AsyncSession, guide_id: uuid.UUID) -> TroubleshootingSession:
    guide = await load_guide(db, guide_id)
    if guide is None:
        raise SessionError(404, "Guide not found.")
    if guide.status is not GuideStatus.READY:
        raise SessionError(409, "This guide has no steps (insufficient evidence); a session cannot be started.")
    start = start_node(guide)
    ts = TroubleshootingSession(guide_id=guide.id, current_node_id=start.id if start else None)
    ts.steps = []
    db.add(ts)
    await db.commit()
    return ts


async def _next_sequence(db: AsyncSession, session_id: uuid.UUID) -> int:
    current = await db.scalar(select(func.max(SessionStep.sequence)).where(SessionStep.session_id == session_id))
    return (current or 0) + 1


async def _open_session(db: AsyncSession, session_id: uuid.UUID) -> TroubleshootingSession:
    ts = await db.scalar(
        select(TroubleshootingSession).where(TroubleshootingSession.id == session_id).with_for_update()
    )
    if ts is None:
        raise SessionError(404, "Session not found.")
    if ts.status is not SessionStatus.IN_PROGRESS:
        raise SessionError(409, "This session is already completed.")
    return ts


async def record_step(db: AsyncSession, session_id: uuid.UUID, body: StepRequest) -> None:
    ts = await _open_session(db, session_id)
    sequence = await _next_sequence(db, session_id)

    if body.type == "observation":
        if not body.observation and not body.action_taken:
            raise SessionError(422, "An observation or an action taken is required.")
        db.add(SessionStep(session_id=ts.id, sequence=sequence, step_type=SessionStepType.OBSERVATION,
                           node_id=ts.current_node_id, observation=body.observation,
                           action_taken=body.action_taken))
        await db.commit()
        return

    guide = await load_guide(db, ts.guide_id)
    assert guide is not None
    nodes = {n.id: n for n in guide.nodes}

    if body.type == "answer":
        if not body.answer_label:
            raise SessionError(422, "answer_label is required.")
        current = nodes.get(ts.current_node_id) if ts.current_node_id else None
        if current is None:
            raise SessionError(409, "The session has no current step.")
        if current.node_type in (GuideNodeType.RESOLUTION, GuideNodeType.ESCALATION):
            raise SessionError(409, "This is an end point; complete the session instead.")
        edge = await db.scalar(
            select(GuideEdge).where(GuideEdge.source_node_id == current.id,
                                    func.lower(GuideEdge.answer_label) == body.answer_label.lower())
        )
        if edge is None:
            allowed = ", ".join(current.expected_answers) or "none"
            raise SessionError(422, f"'{body.answer_label}' is not an answer for this step (allowed: {allowed}).")
        db.add(SessionStep(session_id=ts.id, sequence=sequence, step_type=SessionStepType.ANSWER,
                           node_id=current.id, answer_label=edge.answer_label, target_node_id=edge.target_node_id,
                           observation=body.observation, action_taken=body.action_taken))
        ts.current_node_id = edge.target_node_id
        ts.updated_at = datetime.now(UTC)
        await db.commit()
        return

    # back / revise
    loaded = await load_session(db, session_id)
    assert loaded is not None
    start = start_node(guide)
    path = active_path(loaded, start.id if start else None)
    if len(path) < 2:
        raise SessionError(409, "Already at the first step.")
    target = body.to_node_id or path[-2]
    if target not in path[:-1]:
        raise SessionError(422, "You can only go back to a step on the current path.")
    keep = path.index(target)  # answers that led beyond this step are superseded
    active_answers = [s for s in loaded.steps if s.step_type is SessionStepType.ANSWER and not s.superseded]
    for step in active_answers[keep:]:
        step.superseded = True
    db.add(SessionStep(session_id=ts.id, sequence=sequence, step_type=SessionStepType.BACK,
                       node_id=target, observation=body.observation))
    ts.current_node_id = target
    ts.updated_at = datetime.now(UTC)
    await db.commit()


async def complete_session(db: AsyncSession, session_id: uuid.UUID, body: CompleteSessionRequest) -> None:
    ts = await _open_session(db, session_id)
    sequence = await _next_sequence(db, session_id)
    now = datetime.now(UTC)
    ts.status = SessionStatus.RESOLVED if body.outcome == "resolved" else SessionStatus.UNRESOLVED
    ts.outcome_summary = body.summary
    ts.action_taken = body.action_taken
    ts.completed_at = now
    ts.updated_at = now
    db.add(SessionStep(session_id=ts.id, sequence=sequence, step_type=SessionStepType.COMPLETE,
                       node_id=ts.current_node_id, observation=body.observation, action_taken=body.action_taken))
    await db.commit()
