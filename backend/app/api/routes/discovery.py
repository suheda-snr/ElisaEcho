import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession, PaginationDep, SettingsDep, require_development
from app.db.session import DatabaseNotConfiguredError
from app.db.url import InvalidDatabaseUrlError
from app.schemas.common import Page
from app.schemas.discovery import (
    AnalysisQueueStatus,
    DiscoveryEventRead,
    DiscoveryStatus,
    ResetResult,
    SimulationCommandResult,
    SimulationStatus,
    ThreadDiscovery,
)
from app.services.discovery.demo_reset import reset_demo_data
from app.services.discovery.engine import DiscoveryEngine
from app.services.discovery.overview import discovery_metrics, thread_discoveries

logger = logging.getLogger(__name__)

router = APIRouter(tags=["discovery"])


def get_discovery_engine(request: Request) -> DiscoveryEngine:
    return request.app.state.discovery


EngineDep = Annotated[DiscoveryEngine, Depends(get_discovery_engine)]
DevOnly = [Depends(require_development)]
_DEV_ONLY = {403: {"description": "Not available outside development"}}


def _simulation(engine: DiscoveryEngine) -> SimulationStatus:
    s = engine.simulation
    return SimulationStatus(
        running=s.running,
        started_at=s.started_at,
        finished_at=s.finished_at,
        delivered=s.delivered,
        skipped_duplicates=s.skipped_duplicates,
        total=s.total,
        message_interval_seconds=engine.message_interval_seconds,
        last_error=s.last_error,
    )


@router.get("/discovery/status", response_model=DiscoveryStatus, summary="Pipeline status and metrics")
async def discovery_status(engine: EngineDep, settings: SettingsDep) -> DiscoveryStatus:
    """Works even without a database: metrics are then null and `metrics_error` explains why."""
    metrics, metrics_error = None, None
    try:
        async with engine.session_factory() as session:
            metrics = await discovery_metrics(session)
    except (DatabaseNotConfiguredError, InvalidDatabaseUrlError):
        metrics_error = "Database is not configured."
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Could not load discovery metrics: %s", type(exc).__name__)
        metrics_error = "Database is unavailable."

    gemini = engine.gemini_factory()
    return DiscoveryStatus(
        simulation=_simulation(engine),
        analysis=AnalysisQueueStatus(
            gemini_configured=gemini.configured,
            model=gemini.model,
            embedding_model=engine.embedder_factory().model if engine.embedder_factory else None,
            queued=engine.queued,
            analyzing=engine.analyzing,
            debounce_seconds=engine.debounce_seconds,
            paused_until=engine.gemini_paused_until if engine.gemini_paused else None,
            pause_reason=engine.gemini_pause_reason if engine.gemini_paused else None,
        ),
        metrics=metrics,
        metrics_error=metrics_error,
        development_controls=settings.is_development,
    )


@router.get("/discovery/events", response_model=list[DiscoveryEventRead], summary="Recent pipeline events")
async def discovery_events(
    engine: EngineDep,
    after: Annotated[int, Query(ge=0, description="Return events with a larger id")] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[DiscoveryEventRead]:
    return [DiscoveryEventRead(**vars(e)) for e in engine.events_after(after, limit)]


@router.get("/discovery/threads", response_model=Page[ThreadDiscovery], summary="Threads with discovery results")
async def discovery_threads(
    session: DbSession, page: PaginationDep, source_id: uuid.UUID | None = None
) -> Page[ThreadDiscovery]:
    items, total = await thread_discoveries(session, limit=page.limit, offset=page.offset, source_id=source_id)
    return Page[ThreadDiscovery](items=items, total=total, limit=page.limit, offset=page.offset)


@router.post(
    "/simulation/start",
    response_model=SimulationCommandResult,
    dependencies=DevOnly,
    responses=_DEV_ONLY,
    summary="Start the simulated live feed (development only)",
)
async def start_simulation(engine: EngineDep) -> SimulationCommandResult:
    try:
        async with engine.session_factory():  # fail fast with 503 if not configured
            pass
    except (DatabaseNotConfiguredError, InvalidDatabaseUrlError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured.") from None
    changed = engine.start_simulation()
    return SimulationCommandResult(changed=changed, simulation=_simulation(engine))


@router.post(
    "/simulation/stop",
    response_model=SimulationCommandResult,
    dependencies=DevOnly,
    responses=_DEV_ONLY,
    summary="Stop the simulated live feed (development only)",
)
async def stop_simulation(engine: EngineDep) -> SimulationCommandResult:
    changed = await engine.stop_simulation()
    return SimulationCommandResult(changed=changed, simulation=_simulation(engine))


@router.post(
    "/simulation/reset",
    response_model=ResetResult,
    dependencies=DevOnly,
    responses=_DEV_ONLY,
    summary="Delete synthetic demo conversations and their discoveries (development only)",
)
async def reset_simulation(engine: EngineDep, session: DbSession, settings: SettingsDep) -> ResetResult:
    await engine.stop_simulation()
    await engine.cancel_pending()
    summary = await reset_demo_data(session, settings)
    await session.commit()
    engine.clear_events()
    engine.emit("demo_reset", f"Demo reset: removed {summary.threads} synthetic threads and "
                              f"{summary.knowledge_items} knowledge items")
    return ResetResult(**vars(summary))
