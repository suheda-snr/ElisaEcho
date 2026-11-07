"""Discovery engine: simulation start/stop and debounced analysis (no DB, no Gemini)."""

import asyncio
import uuid
from contextlib import asynccontextmanager

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.main import app
from app.services.discovery.analyzer import AnalysisOutcome
from app.services.discovery.engine import DiscoveryEngine, interleaved_demo_messages
from app.seed.demo_data import DEMO_THREADS
from tests.discovery_fakes import FakeGemini, IRRELEVANT


@asynccontextmanager
async def no_session():
    yield None


def make_engine(**kwargs) -> DiscoveryEngine:
    return DiscoveryEngine(session_factory=no_session, gemini_factory=lambda: FakeGemini(IRRELEVANT), **kwargs)


async def wait_for(predicate, timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.005)


def test_demo_messages_are_interleaved_across_threads() -> None:
    plan = interleaved_demo_messages()
    assert len(plan) == sum(len(t.messages) for t in DEMO_THREADS)
    first_round = [t.external_id for t, _ in plan[: len(DEMO_THREADS)]]
    assert first_round == [t.external_id for t in DEMO_THREADS]  # all threads progress together
    for thread in DEMO_THREADS:  # order within each thread is preserved
        assert [m for t, m in plan if t is thread] == list(thread.messages)
    # The Site 42 confirmation arrives last, after the other conversations.
    deferred = [m.external_id for _, m in plan if m.deferred]
    assert deferred and [m.external_id for _, m in plan[-len(deferred):]] == deferred


async def test_feed_pauses_before_deferred_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = make_engine(message_interval_seconds=0.0, debounce_seconds=0.05)
    order: list[str] = []

    async def fake_deliver(thread, message, ids):
        order.append(message.external_id)
        return True

    monkeypatch.setattr(engine, "_deliver", fake_deliver)
    engine.start_simulation()
    await wait_for(lambda: not engine.simulation.running, timeout=5)
    assert order == [m.external_id for _, m in interleaved_demo_messages()]
    assert any("tries the suggested fix" in e.message for e in engine.events_after(0))


async def test_quota_pause_defers_analyses_without_calling_gemini() -> None:
    calls: list[uuid.UUID] = []

    async def quota_exhausted(session, thread_id, gemini, force=False):
        calls.append(thread_id)
        return AnalysisOutcome(thread_id=thread_id, status="failed",
                               error="Gemini quota exhausted. Try again in about 12 h.",
                               retry_after_seconds=43000)

    engine = make_engine(analyze=quota_exhausted)
    first = await engine.run_analysis(uuid.uuid4())
    assert first.status == "failed" and engine.gemini_paused
    second = await engine.run_analysis(uuid.uuid4())
    assert second.status == "deferred" and len(calls) == 1  # no further requests while paused
    assert "quota" in (engine.gemini_pause_reason or "")

    engine.gemini_paused_until = engine.gemini_paused_until.replace(year=2000)  # quota window over
    assert not engine.gemini_paused


async def test_simulation_start_stop_and_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = make_engine(message_interval_seconds=0.01, debounce_seconds=0.01)
    delivered: list[str] = []

    async def fake_deliver(thread, message, ids):
        delivered.append(message.external_id)
        return True

    monkeypatch.setattr(engine, "_deliver", fake_deliver)

    assert engine.start_simulation() is True
    assert engine.simulation.running
    assert engine.start_simulation() is False  # already running: no second feed
    await wait_for(lambda: len(delivered) >= 3)

    assert await engine.stop_simulation() is True
    assert not engine.simulation.running
    stopped_at = len(delivered)
    await asyncio.sleep(0.05)
    assert len(delivered) == stopped_at  # really stopped
    assert await engine.stop_simulation() is False
    assert any(e.kind == "simulation_stopped" for e in engine.events_after(0))

    assert engine.start_simulation() is True  # restart works
    await wait_for(lambda: not engine.simulation.running, timeout=6)  # includes the feed pause
    assert engine.simulation.finished_at is not None
    assert engine.simulation.total == len(interleaved_demo_messages())


async def test_burst_of_messages_triggers_one_analysis() -> None:
    calls: list[uuid.UUID] = []

    async def fake_analyze(session, thread_id, gemini, force=False):
        calls.append(thread_id)
        return AnalysisOutcome(thread_id=thread_id, status="unchanged")

    engine = make_engine(debounce_seconds=0.05, analyze=fake_analyze)
    thread = uuid.uuid4()
    for _ in range(5):
        engine.schedule_analysis(thread, "T")
        await asyncio.sleep(0.01)
    assert engine.queued == 1
    await wait_for(lambda: len(calls) == 1 and engine.queued == 0)
    await asyncio.sleep(0.1)
    assert calls == [thread]


async def test_update_during_analysis_triggers_one_rerun() -> None:
    started, release = asyncio.Event(), asyncio.Event()
    calls: list[uuid.UUID] = []

    async def slow_analyze(session, thread_id, gemini, force=False):
        calls.append(thread_id)
        started.set()
        await release.wait()
        return AnalysisOutcome(thread_id=thread_id, status="analyzed", detection_status="rejected")

    engine = make_engine(debounce_seconds=0.01, analyze=slow_analyze)
    thread = uuid.uuid4()
    engine.schedule_analysis(thread)
    await started.wait()
    engine.schedule_analysis(thread)  # new message while Gemini is working
    await asyncio.sleep(0.05)
    assert len(calls) == 1  # not analyzed concurrently
    release.set()
    await wait_for(lambda: len(calls) == 2)


async def test_analysis_errors_become_events_not_crashes() -> None:
    async def broken(session, thread_id, gemini, force=False):
        raise RuntimeError("boom")

    engine = make_engine(analyze=broken)
    outcome = await engine.run_analysis(uuid.uuid4())
    assert outcome.status == "failed"
    assert engine.events_after(0)[-1].kind == "analysis_failed"


@pytest.mark.parametrize("path", ["/api/simulation/start", "/api/simulation/stop", "/api/simulation/reset",
                                  f"/api/threads/{uuid.uuid4()}/analyze"])
async def test_control_endpoints_are_development_only(client_without_db_access: httpx.AsyncClient, path: str) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="production")
    response = await client_without_db_access.post(path)
    assert response.status_code == 403


async def test_status_works_without_database(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/discovery/status")
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"] is None and body["metrics_error"] == "Database is not configured."
    assert body["analysis"]["gemini_configured"] is False
    assert "key" not in str(body["analysis"]).lower()
