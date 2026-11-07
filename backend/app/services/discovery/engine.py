"""In-process discovery engine: simulated live feed, debounced analysis, event log.

Development MVP. Everything runs inside the API process with asyncio tasks, so it only
works with a single backend process and is lost on restart. A production deployment would
use a durable queue and worker (e.g. a jobs table polled with SKIP LOCKED) instead.
"""

import asyncio
import itertools
import logging
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiClient
from app.models import ConversationThread, Message
from app.schemas.threads import MessageIngest, ThreadIngest
from app.seed.demo_data import (
    DEMO_SOURCE_EXTERNAL_ID,
    DEMO_SOURCE_NAME,
    DEMO_SOURCE_TYPE,
    DEMO_THREADS,
    DemoMessage,
    DemoThread,
    demo_message_url,
)
from app.services.discovery.analyzer import AnalysisOutcome, analyze_thread
from app.services.ingestion import upsert_messages, upsert_source, upsert_thread
from app.services.retrieval.indexing import IndexOutcome, index_item

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
EventKind = Literal[
    "simulation_started", "simulation_stopped", "simulation_finished", "message_received",
    "duplicate_skipped", "analysis_scheduled", "analysis_started", "analysis_completed",
    "analysis_skipped", "analysis_failed", "demo_reset", "error", "indexed", "index_pending",
]


@dataclass(frozen=True)
class DiscoveryEvent:
    id: int
    at: datetime
    kind: EventKind
    message: str
    thread_id: uuid.UUID | None = None
    thread_title: str | None = None
    level: Literal["info", "success", "warning", "error"] = "info"


@dataclass
class SimulationState:
    running: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    delivered: int = 0
    skipped_duplicates: int = 0
    total: int = 0
    last_error: str | None = None


def interleaved_demo_messages(threads: tuple[DemoThread, ...] = DEMO_THREADS) -> list[tuple[DemoThread, DemoMessage]]:
    """Round-robin across threads so several conversations progress at the same time;
    messages marked `deferred` follow once the others are done (order within a thread kept)."""
    columns = [[(t, m) for m in t.messages if not m.deferred] for t in threads]
    live = [pair for row in itertools.zip_longest(*columns) for pair in row if pair is not None]
    return live + [(t, m) for t in threads for m in t.messages if m.deferred]


@dataclass
class DiscoveryEngine:
    session_factory: SessionFactory
    gemini_factory: Callable[[], GeminiClient]
    debounce_seconds: float = 12.0
    message_interval_seconds: float = 2.0
    max_concurrent_analyses: int = 2
    analyze: Callable[..., Awaitable[AnalysisOutcome]] = analyze_thread
    # Optional observer for every emitted event (the Slack worker mirrors results to the DB).
    on_event: Callable[[DiscoveryEvent], None] | None = None
    # Search indexing after knowledge changes (Phase 4). None disables it.
    embedder_factory: Callable[[], EmbeddingService] | None = None
    index: Callable[..., Awaitable[IndexOutcome]] = index_item

    simulation: SimulationState = field(default_factory=SimulationState)
    _events: deque[DiscoveryEvent] = field(default_factory=lambda: deque(maxlen=300))
    _event_ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    _timers: dict[uuid.UUID, asyncio.Task] = field(default_factory=dict)
    _running: set[uuid.UUID] = field(default_factory=set)
    _rerun: set[uuid.UUID] = field(default_factory=set)
    _locks: dict[uuid.UUID, asyncio.Lock] = field(default_factory=dict)
    _titles: dict[uuid.UUID, str | None] = field(default_factory=dict)
    _sim_task: asyncio.Task | None = None
    _semaphore: asyncio.Semaphore | None = None
    # While Gemini quota is exhausted, analyses are deferred instead of burning requests.
    gemini_paused_until: datetime | None = None
    gemini_pause_reason: str | None = None

    # ---- events ---------------------------------------------------------------------------

    def emit(self, kind: EventKind, message: str, *, thread_id: uuid.UUID | None = None,
             level: Literal["info", "success", "warning", "error"] = "info") -> None:
        event = DiscoveryEvent(
            id=next(self._event_ids), at=datetime.now(UTC), kind=kind, message=message,
            thread_id=thread_id, thread_title=self._titles.get(thread_id) if thread_id else None,
            level=level,
        )
        self._events.append(event)
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception:  # noqa: BLE001 - observers must never break the pipeline
                logger.exception("Discovery event observer failed")

    def events_after(self, after: int = 0, limit: int = 100) -> list[DiscoveryEvent]:
        # A cursor beyond the newest event means the backend restarted (ids begin at 1
        # again): send the recent history instead of nothing.
        if self._events and after > self._events[-1].id:
            after = 0
        return [e for e in self._events if e.id > after][-limit:]

    @property
    def queued(self) -> int:
        return len(self._timers)

    @property
    def analyzing(self) -> int:
        return len(self._running)

    # ---- analysis -------------------------------------------------------------------------

    def schedule_analysis(self, thread_id: uuid.UUID, title: str | None = None) -> None:
        """Debounce: (re)start the timer so a burst of messages becomes one analysis."""
        if title is not None:
            self._titles[thread_id] = title
        existing = self._timers.pop(thread_id, None)
        if existing is not None:
            existing.cancel()
        self._timers[thread_id] = asyncio.create_task(self._delayed(thread_id))

    async def _delayed(self, thread_id: uuid.UUID) -> None:
        try:
            await asyncio.sleep(self.debounce_seconds)
        except asyncio.CancelledError:
            return
        if self._timers.get(thread_id) is asyncio.current_task():
            del self._timers[thread_id]
        if thread_id in self._running:
            self._rerun.add(thread_id)  # analyze again once the current run finishes
            return
        await self.run_analysis(thread_id)

    async def run_analysis(self, thread_id: uuid.UUID, *, force: bool = False) -> AnalysisOutcome:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(max(1, self.max_concurrent_analyses))
        if self.gemini_paused:
            outcome = AnalysisOutcome(
                thread_id=thread_id, status="deferred",
                error=f"Gemini paused until {self.gemini_paused_until:%H:%M} UTC: {self.gemini_pause_reason}",
            )
            self._report(outcome)
            return outcome
        lock = self._locks.setdefault(thread_id, asyncio.Lock())
        async with lock, self._semaphore:
            self._running.add(thread_id)
            self.emit("analysis_started", "Checking conversation for new content", thread_id=thread_id)
            try:
                try:
                    async with self.session_factory() as session:
                        outcome = await self.analyze(session, thread_id, self.gemini_factory(), force=force)
                except Exception as exc:  # noqa: BLE001 - surface, never crash the engine
                    logger.exception("Unexpected analysis error for thread %s", thread_id)
                    outcome = AnalysisOutcome(thread_id=thread_id, status="failed", error=type(exc).__name__)
                self._report(outcome)
                # Indexing counts as part of the analysis, so "idle" really means searchable.
                if outcome.status == "analyzed" and outcome.knowledge_item_id is not None:
                    await self._index_knowledge(thread_id, outcome.knowledge_item_id)
            finally:
                self._running.discard(thread_id)

        if thread_id in self._rerun:
            self._rerun.discard(thread_id)
            self.schedule_analysis(thread_id)
        return outcome

    @property
    def gemini_paused(self) -> bool:
        if self.gemini_paused_until is None:
            return False
        if datetime.now(UTC) >= self.gemini_paused_until:
            self.gemini_paused_until = self.gemini_pause_reason = None
            return False
        return True

    async def _index_knowledge(self, thread_id: uuid.UUID, item_id: uuid.UUID) -> None:
        """Embed new/changed knowledge for search. Failures leave chunks pending for a later
        retry (backfill command); the extracted knowledge itself is already saved."""
        if self.embedder_factory is None:
            return
        try:
            async with self.session_factory() as session:
                result = await self.index(session, item_id, self.embedder_factory())
        except Exception as exc:  # noqa: BLE001 - indexing must never break discovery
            logger.exception("Indexing failed for knowledge item %s", item_id)
            self.emit("index_pending", f"Search indexing failed ({type(exc).__name__}); will retry later",
                      thread_id=thread_id, level="warning")
            return
        if result.status == "indexed":
            self.emit("indexed", f"Embedded for semantic search ({result.embedded} chunk(s))",
                      thread_id=thread_id, level="success")
        elif result.status == "pending":
            self.emit("index_pending", f"Saved; embedding pending: {result.error or 'retry later'}",
                      thread_id=thread_id, level="warning")

    def _report(self, outcome: AnalysisOutcome) -> None:
        tid = outcome.thread_id
        if outcome.retry_after_seconds and outcome.retry_after_seconds > 0:
            self.gemini_paused_until = datetime.now(UTC) + timedelta(seconds=outcome.retry_after_seconds)
            self.gemini_pause_reason = outcome.error
            self.emit("analysis_failed", f"Pausing Gemini calls until {self.gemini_paused_until:%H:%M} UTC "
                      "(quota). Conversations keep being ingested.", level="warning")
        if outcome.status == "analyzed":
            if outcome.detection_status == "rejected":
                self.emit("analysis_completed", "No operational knowledge found; conversation ignored",
                          thread_id=tid)
            elif outcome.knowledge_item_id:
                status = (outcome.resolution_status or "unknown").replace("_", " ")
                self.emit("analysis_completed", f"Knowledge saved ({status})", thread_id=tid, level="success")
            else:
                self.emit("analysis_completed", "Technical issue detected; resolution not yet known",
                          thread_id=tid, level="warning")
        elif outcome.status in ("unchanged", "empty"):
            self.emit("analysis_skipped", "No new content since last analysis; Gemini not called",
                      thread_id=tid)
        elif outcome.status == "deferred":
            self.emit("analysis_skipped", outcome.error or "Gemini paused", thread_id=tid, level="warning")
        elif outcome.status == "not_configured":
            self.emit("analysis_skipped", outcome.error or "Gemini is not configured", thread_id=tid,
                      level="warning")
        else:
            self.emit("analysis_failed", outcome.error or "Analysis failed", thread_id=tid, level="error")

    # ---- simulation -----------------------------------------------------------------------

    def start_simulation(self) -> bool:
        """Start delivering demo messages. Returns False if it is already running."""
        if self._sim_task is not None and not self._sim_task.done():
            return False
        plan = interleaved_demo_messages()
        self.simulation = SimulationState(running=True, started_at=datetime.now(UTC), total=len(plan))
        self._sim_task = asyncio.create_task(self._simulate(plan))
        self.emit("simulation_started", f"Simulated feed started ({len(plan)} messages, synthetic data)")
        return True

    async def stop_simulation(self) -> bool:
        task = self._sim_task
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    async def _simulate(self, plan: list[tuple[DemoThread, DemoMessage]]) -> None:
        thread_ids: dict[str, uuid.UUID] = {}
        try:
            paused = False
            for demo_thread, demo_message in plan:
                if demo_message.deferred and not paused:
                    paused = True
                    wait = self.debounce_seconds + 2
                    self.emit("analysis_scheduled",
                              f"Feed quiet for {wait:.0f} s while the engineer tries the suggested fix")
                    await asyncio.sleep(wait)
                started = asyncio.get_running_loop().time()
                delivered = await self._deliver(demo_thread, demo_message, thread_ids)
                if delivered:
                    # Fixed cadence: database round trips count towards the interval, so the
                    # per-thread gap stays below the analysis debounce.
                    elapsed = asyncio.get_running_loop().time() - started
                    await asyncio.sleep(max(0.0, self.message_interval_seconds - elapsed))
            self.simulation.finished_at = datetime.now(UTC)
            self.emit("simulation_finished", "All simulated messages delivered")
        except asyncio.CancelledError:
            self.emit("simulation_stopped", "Simulation stopped")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Simulation failed")
            self.simulation.last_error = type(exc).__name__
            self.emit("error", "Simulation stopped because of an error (is the database reachable?)",
                      level="error")
        finally:
            self.simulation.running = False

    async def _deliver(self, demo_thread: DemoThread, demo_message: DemoMessage,
                       thread_ids: dict[str, uuid.UUID]) -> bool:
        async with self.session_factory() as session:
            thread_id = thread_ids.get(demo_thread.external_id)
            if thread_id is None:
                source_id = await upsert_source(
                    session, name=DEMO_SOURCE_NAME, source_type=DEMO_SOURCE_TYPE,
                    external_source_id=DEMO_SOURCE_EXTERNAL_ID,
                )
                thread_id = await upsert_thread(
                    session, source_id,
                    ThreadIngest(external_thread_id=demo_thread.external_id, title=demo_thread.title),
                )
                thread_ids[demo_thread.external_id] = thread_id
                self._titles[thread_id] = demo_thread.title

            exists = await session.scalar(
                select(Message.id).where(
                    Message.thread_id == thread_id,
                    Message.external_message_id == demo_message.external_id,
                )
            )
            if exists is not None:
                await session.commit()
                self.simulation.skipped_duplicates += 1
                self.emit("duplicate_skipped", "Already ingested; duplicate ignored", thread_id=thread_id)
                self.schedule_analysis(thread_id)  # no-op Gemini-wise if the thread is unchanged
                return False

            await upsert_messages(session, thread_id, [MessageIngest(
                external_message_id=demo_message.external_id,
                author_external_id=demo_message.author_id,
                author_display_name=demo_message.author_name,
                content=demo_message.content,
                sent_at=demo_message.sent_at,
                source_url=demo_message_url(demo_thread.external_id, demo_message.external_id),
            )])
            await session.commit()

        self.simulation.delivered += 1
        self.emit("message_received", f"{demo_message.author_name}: {demo_message.content[:80]}",
                  thread_id=thread_id)
        self.schedule_analysis(thread_id)
        return True

    # ---- lifecycle ------------------------------------------------------------------------

    async def cancel_pending(self) -> None:
        for task in list(self._timers.values()):
            task.cancel()
        self._timers.clear()
        self._rerun.clear()

    def clear_events(self) -> None:
        self._events.clear()

    async def shutdown(self) -> None:
        await self.stop_simulation()
        await self.cancel_pending()


async def thread_title(session: AsyncSession, thread_id: uuid.UUID) -> str | None:
    return await session.scalar(select(ConversationThread.title).where(ConversationThread.id == thread_id))
