"""Troubleshooting feedback (Phase 6C): did a recommendation work?

There is no user authentication in this MVP. Creating feedback returns a one-time
`edit_token`; correcting feedback requires it in the `X-Feedback-Token` header, so only the
submitting browser can change a report. `verification_status` cannot be set by clients
(always `self_reported`; no verification workflow exists yet).
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.api.deps import DbSession, PaginationDep
from app.models import KnowledgeItem
from app.schemas.common import Page
from app.schemas.feedback import FeedbackCreate, FeedbackRead, FeedbackSaved, FeedbackSummary, FeedbackUpdate
from app.services.feedback.service import (
    FeedbackError,
    feedback_reads,
    knowledge_feedback,
    session_feedback,
    submit_feedback,
    update_feedback,
)
from app.services.feedback.summary import feedback_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["troubleshooting feedback"])

TokenHeader = Annotated[str | None, Header(alias="X-Feedback-Token", max_length=200)]


def _after_save(request: Request, knowledge_id: uuid.UUID) -> None:
    """Refresh the knowledge group summary in the background. Feedback is already committed,
    so a failure here (e.g. Gemini unavailable) never loses it."""
    engine = getattr(request.app.state, "discovery", None)
    try:
        if engine is not None:
            engine.schedule_feedback_refresh(knowledge_id)
    except Exception:  # noqa: BLE001
        logger.exception("Could not schedule group refresh after feedback")


@router.post("/troubleshooting/feedback", response_model=FeedbackSaved,
             summary="Report whether a recommendation was attempted and what happened",
             responses={200: {"description": "Identical feedback already existed (or a correction with the token)"},
                        201: {"description": "Feedback recorded"},
                        404: {"description": "Session or knowledge not found"},
                        409: {"description": "Step not reached, or different feedback already submitted"},
                        422: {"description": "Invalid combination or unrelated knowledge"}})
async def create_feedback(body: FeedbackCreate, db: DbSession, request: Request, response: Response,
                          token: TokenHeader = None) -> FeedbackSaved:
    try:
        result = await submit_feedback(db, body, token)
    except FeedbackError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    _after_save(request, body.knowledge_item_id)
    read = (await feedback_reads(db, [result.feedback]))[0]
    return FeedbackSaved(**read.model_dump(), created=result.created, edit_token=result.edit_token)


@router.patch("/troubleshooting/feedback/{feedback_id}", response_model=FeedbackRead,
              summary="Correct previously submitted feedback (requires X-Feedback-Token)",
              responses={403: {"description": "Missing or invalid edit token"}, 404: {"description": "Not found"}})
async def correct_feedback(feedback_id: uuid.UUID, body: FeedbackUpdate, db: DbSession, request: Request,
                           token: TokenHeader = None) -> FeedbackRead:
    try:
        row = await update_feedback(db, feedback_id, body, token)
    except FeedbackError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    _after_save(request, row.knowledge_item_id)
    return (await feedback_reads(db, [row]))[0]


@router.get("/troubleshooting/sessions/{session_id}/feedback", response_model=list[FeedbackRead],
            summary="Feedback given in a session", responses={404: {"description": "Session not found"}})
async def get_session_feedback(session_id: uuid.UUID, db: DbSession) -> list[FeedbackRead]:
    rows = await session_feedback(db, session_id)
    if rows is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    return rows


async def _knowledge_or_404(db: DbSession, knowledge_id: uuid.UUID) -> None:
    if await db.get(KnowledgeItem, knowledge_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge item not found.")


@router.get("/knowledge/{knowledge_id}/feedback", response_model=Page[FeedbackRead],
            summary="Troubleshooting feedback records for a knowledge item")
async def get_knowledge_feedback(knowledge_id: uuid.UUID, db: DbSession, page: PaginationDep) -> Page[FeedbackRead]:
    await _knowledge_or_404(db, knowledge_id)
    items, total = await knowledge_feedback(db, knowledge_id, limit=page.limit, offset=page.offset)
    return Page[FeedbackRead](items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/knowledge/{knowledge_id}/feedback/summary", response_model=FeedbackSummary,
            summary="Aggregated real-world feedback for a knowledge item")
async def get_feedback_summary(knowledge_id: uuid.UUID, db: DbSession) -> FeedbackSummary:
    await _knowledge_or_404(db, knowledge_id)
    return await feedback_summary(db, knowledge_id)
