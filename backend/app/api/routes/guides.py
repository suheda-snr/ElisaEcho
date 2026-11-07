import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiError, GeminiNotConfiguredError
from app.api.deps import DbSession, PaginationDep, SettingsDep
from app.api.routes.search import get_embedding_service
from app.models import TroubleshootingGuide, TroubleshootingSession
from app.schemas.common import Page
from app.schemas.guides import (
    CompleteSessionRequest,
    CreateSessionRequest,
    GenerateGuideRequest,
    GuideRead,
    GuideSummary,
    SessionDetail,
    SessionSummary,
    StepRequest,
)
from app.services.guides.generator import GuideGenerationError, generate_guide
from app.services.guides.read import guide_read, load_guide, load_session, session_read, start_node
from app.services.guides.sessions import SessionError, complete_session, create_session, record_step

router = APIRouter(tags=["guided troubleshooting"])

EmbedderDep = Annotated[EmbeddingService, Depends(get_embedding_service)]


async def _guide_or_404(db: AsyncSession, guide_id: uuid.UUID) -> GuideRead:
    guide = await load_guide(db, guide_id)
    if guide is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Guide not found.")
    return await guide_read(db, guide)


@router.post(
    "/guides/generate",
    response_model=GuideRead,
    summary="Generate an evidence-backed troubleshooting guide",
    responses={502: {"description": "AI output invalid; nothing saved"},
               503: {"description": "Gemini unavailable"}},
)
async def generate(
    body: GenerateGuideRequest, db: DbSession, settings: SettingsDep, embedder: EmbedderDep
) -> GuideRead:
    """Retrieves relevant knowledge (Phase 4 hybrid search) and asks Gemini for a decision tree
    built only from it. Returns `status=insufficient_evidence` with no steps if nothing relevant
    is known. Evidence and approval status of every step are validated server-side."""
    try:
        guide = await generate_guide(
            db,
            problem=body.problem,
            equipment_identifier=body.equipment_identifier or None,
            embedder=embedder,
            gemini=embedder.gemini,
            min_similarity=settings.search_min_similarity,
            similarity_margin=settings.search_similarity_margin,
            pool=settings.search_candidate_pool,
        )
    except GeminiNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    except GeminiError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Guide generation unavailable: {exc}") from None
    except GuideGenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    return await _guide_or_404(db, guide.id)


@router.get("/guides", response_model=Page[GuideSummary], summary="Recent guides")
async def list_guides(db: DbSession, page: PaginationDep) -> Page[GuideSummary]:
    total = int(await db.scalar(select(func.count()).select_from(TroubleshootingGuide)) or 0)
    rows = await db.scalars(
        select(TroubleshootingGuide).order_by(TroubleshootingGuide.created_at.desc())
        .limit(page.limit).offset(page.offset)
    )
    return Page[GuideSummary](
        items=[GuideSummary.model_validate(g, from_attributes=True) for g in rows],
        total=total, limit=page.limit, offset=page.offset,
    )


@router.get("/guides/{guide_id}", response_model=GuideRead, summary="Get a guide",
            responses={404: {"description": "Guide not found"}})
async def get_guide(guide_id: uuid.UUID, db: DbSession) -> GuideRead:
    return await _guide_or_404(db, guide_id)


async def _session_detail(db: AsyncSession, session_id: uuid.UUID) -> SessionDetail:
    ts = await load_session(db, session_id)
    if ts is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    guide = await load_guide(db, ts.guide_id)
    assert guide is not None
    start = start_node(guide)
    read = session_read(ts, start.id if start else None)
    return SessionDetail(**read.model_dump(), guide=await guide_read(db, guide))


@router.post("/troubleshooting/sessions", response_model=SessionDetail, status_code=status.HTTP_201_CREATED,
             summary="Start a troubleshooting session for a guide",
             responses={404: {"description": "Guide not found"}, 409: {"description": "Guide has no steps"}})
async def start_session(body: CreateSessionRequest, db: DbSession) -> SessionDetail:
    try:
        ts = await create_session(db, body.guide_id)
    except SessionError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return await _session_detail(db, ts.id)


@router.get("/troubleshooting/sessions", response_model=Page[SessionSummary], summary="Recent sessions")
async def list_sessions(db: DbSession, page: PaginationDep) -> Page[SessionSummary]:
    total = int(await db.scalar(select(func.count()).select_from(TroubleshootingSession)) or 0)
    rows = await db.execute(
        select(TroubleshootingSession, TroubleshootingGuide)
        .join(TroubleshootingGuide, TroubleshootingSession.guide_id == TroubleshootingGuide.id)
        .order_by(TroubleshootingSession.updated_at.desc())
        .limit(page.limit).offset(page.offset)
    )
    items = [
        SessionSummary(id=ts.id, guide_id=g.id, guide_title=g.title, problem_description=g.problem_description,
                       status=ts.status, updated_at=ts.updated_at)
        for ts, g in rows
    ]
    return Page[SessionSummary](items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/troubleshooting/sessions/{session_id}", response_model=SessionDetail, summary="Get a session",
            responses={404: {"description": "Session not found"}})
async def get_session(session_id: uuid.UUID, db: DbSession) -> SessionDetail:
    return await _session_detail(db, session_id)


@router.post("/troubleshooting/sessions/{session_id}/steps", response_model=SessionDetail,
             summary="Answer the current step, add an observation, or go back",
             responses={404: {"description": "Not found"}, 409: {"description": "Not allowed now"}})
async def add_step(session_id: uuid.UUID, body: StepRequest, db: DbSession) -> SessionDetail:
    try:
        await record_step(db, session_id, body)
    except SessionError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, exc.message) from None
    return await _session_detail(db, session_id)


@router.post("/troubleshooting/sessions/{session_id}/complete", response_model=SessionDetail,
             summary="Complete a session with the engineer's outcome")
async def complete(session_id: uuid.UUID, body: CompleteSessionRequest, db: DbSession) -> SessionDetail:
    try:
        await complete_session(db, session_id, body)
    except SessionError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, exc.message) from None
    return await _session_detail(db, session_id)
