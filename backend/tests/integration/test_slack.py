"""Slack integration against the isolated test DB. Slack and Gemini are mocked."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.slack.worker as worker_module
from app.api.routes.integrations import get_slack_client
from app.core.config import Settings, get_settings
from app.main import app
from app.models import (
    ConversationThread,
    IntegrationEvent,
    KnowledgeChunk,
    KnowledgeEvidence,
    KnowledgeItem,
    Message,
)
from app.models.enums import ResolutionStatus, ThreadProcessingStatus
from app.services.discovery.engine import DiscoveryEngine
from app.services.integrations import SLACK, get_state, update_state
from app.services.retrieval.search import SearchFilters, hybrid_search
from app.slack.channels import set_channel_monitoring
from app.slack.ingest import SlackIngestor
from tests.discovery_fakes import FakeGemini, act, analysis, ev, message_count
from tests.retrieval_fakes import FakeEmbedder
from tests.slack_fakes import (
    BOT_USER,
    CHANNEL,
    OTHER_CHANNEL,
    TEAM,
    FakeDirectory,
    FakeWebClient,
    envelope,
    message,
)

PARENT = "1762500000.000100"


def shared(db: AsyncSession):
    lock = asyncio.Lock()

    @asynccontextmanager
    async def factory():
        async with lock:
            yield db

    return factory


def ingestor(db: AsyncSession, scheduled: list | None = None, directory: FakeDirectory | None = None) -> SlackIngestor:
    calls = scheduled if scheduled is not None else []
    return SlackIngestor(session_factory=shared(db), directory=directory or FakeDirectory(),
                         schedule_analysis=lambda tid, title: calls.append((tid, title)), bot_user_id=BOT_USER)


async def monitor(db: AsyncSession, channel: str = CHANNEL, enabled: bool = True) -> None:
    await set_channel_monitoring(db, TEAM, channel, f"#{channel.lower()}", enabled=enabled)
    await db.commit()


CONVERSATION = [
    message(PARENT, "The network connection keeps dropping at Site 42."),
    message("1762500060.000200", "Did you try restarting the affected service rather than rebooting the whole router?",
            user="U0BOB0001", thread_ts=PARENT),
    message("1762500300.000300", "Yes, restarting that service fixed it.", thread_ts=PARENT),
]


async def thread_messages(db: AsyncSession) -> list[Message]:
    db.expunge_all()
    return list(await db.scalars(
        select(Message).join(Message.thread).where(ConversationThread.external_thread_id == f"{CHANNEL}:{PARENT}")
        .order_by(Message.sent_at)))


# ---- ingestion ---------------------------------------------------------------------------

async def test_unmonitored_channels_are_not_ingested(db_session: AsyncSession) -> None:
    scheduled: list = []
    result = await ingestor(db_session, scheduled).handle_payload(envelope(CONVERSATION[0]))
    assert result.status == "not_monitored" and scheduled == []
    await monitor(db_session, enabled=False)  # known but disabled
    assert (await ingestor(db_session).handle_payload(envelope(CONVERSATION[0]))).status == "not_monitored"
    assert await thread_messages(db_session) == []


async def test_thread_grouping_order_authors_and_permalinks(db_session: AsyncSession) -> None:
    await monitor(db_session)
    scheduled: list = []
    ing = ingestor(db_session, scheduled)
    for event in reversed(CONVERSATION):  # out of order on purpose
        assert (await ing.handle_payload(envelope(event))).status == "stored"

    messages = await thread_messages(db_session)
    assert [m.external_message_id for m in messages] == [e["ts"] for e in CONVERSATION]  # Slack order
    assert [m.author_display_name for m in messages] == ["Alice (test)", "Bob (test)", "Alice (test)"]
    assert all(m.source_url.startswith("https://test.slack.invalid/archives/") for m in messages)
    thread = await db_session.get(ConversationThread, messages[0].thread_id)
    assert thread.title == "The network connection keeps dropping at Site 42."  # from the parent
    assert len({tid for tid, _ in scheduled}) == 1 and len(scheduled) == 3  # analysis triggered automatically


async def test_duplicate_events_do_not_duplicate_messages(db_session: AsyncSession) -> None:
    await monitor(db_session)
    ing = ingestor(db_session)
    for _ in range(3):
        for event in CONVERSATION:
            await ing.handle_payload(envelope(event))
    assert len(await thread_messages(db_session)) == 3


async def test_channels_and_workspaces_never_share_threads(db_session: AsyncSession) -> None:
    await monitor(db_session)
    await monitor(db_session, OTHER_CHANNEL)
    ing = ingestor(db_session)
    await ing.handle_payload(envelope(message(PARENT, "same ts, channel 1")))
    await ing.handle_payload(envelope(message(PARENT, "same ts, channel 2", channel=OTHER_CHANNEL)))
    other_team = await ing.handle_payload(envelope(message(PARENT, "other workspace"), team="T0OTHER01"))
    assert other_team.status == "not_monitored"
    threads = await db_session.scalar(select(func.count()).select_from(ConversationThread)
                                      .where(ConversationThread.external_thread_id.like(f"%:{PARENT}")))
    assert threads == 2


async def test_bot_messages_are_ignored(db_session: AsyncSession) -> None:
    await monitor(db_session)
    result = await ingestor(db_session).handle_payload(envelope(message(PARENT, "I am a bot", bot_id="B01")))
    assert result.status == "ignored"
    assert await thread_messages(db_session) == []


async def test_edits_and_deletions_update_and_requeue(db_session: AsyncSession) -> None:
    await monitor(db_session)
    ing = ingestor(db_session)
    for event in CONVERSATION:
        await ing.handle_payload(envelope(event))
    thread_id = (await thread_messages(db_session))[0].thread_id
    thread = await db_session.get(ConversationThread, thread_id)
    thread.processing_status = ThreadProcessingStatus.PROCESSED
    await db_session.commit()

    edit = {"type": "message", "subtype": "message_changed", "channel": CHANNEL, "channel_type": "channel",
            "message": {"user": "U0BOB0001", "text": "Restart the DHCP relay service, not the router.",
                        "ts": CONVERSATION[1]["ts"], "thread_ts": PARENT, "edited": {"ts": "1762501000.000000"}}}
    assert (await ing.handle_payload(envelope(edit))).status == "updated"
    messages = await thread_messages(db_session)
    assert messages[1].content == "Restart the DHCP relay service, not the router." and messages[1].edited_at
    thread = await db_session.get(ConversationThread, thread_id, populate_existing=True)
    assert thread.processing_status is ThreadProcessingStatus.PENDING  # re-analysis queued

    deletion = {"type": "message", "subtype": "message_deleted", "channel": CHANNEL, "channel_type": "channel",
                "deleted_ts": CONVERSATION[2]["ts"], "previous_message": {"ts": CONVERSATION[2]["ts"], "thread_ts": PARENT}}
    assert (await ing.handle_payload(envelope(deletion))).status == "deleted"
    assert (await thread_messages(db_session))[2].deleted_at is not None  # kept, marked deleted
    unknown = {**deletion, "deleted_ts": "1.0", "previous_message": {"ts": "1.0"}}
    assert (await ing.handle_payload(envelope(unknown))).status == "unknown_message"


# ---- full pipeline: Slack -> Gemini (mocked) -> knowledge -> embeddings -> search -----------

def slack_responder(contents: str):
    if message_count(contents) < 3:
        return analysis(classification="unverified_suggestion", is_valuable_knowledge=True, title="Restart service",
                        problem_description="Connection drops at Site 42", resolution="Restart the affected service",
                        resolution_status="suggested", attempted_actions=[act("Restart service", "not_attempted", "M2")],
                        evidence=[ev("M1", "problem_report"), ev("M2", "suggested_solution")])
    return analysis(
        classification="confirmed_resolution", is_valuable_knowledge=True,
        title="Restart the affected service instead of rebooting the router",
        problem_description="Network connection keeps dropping at Site 42",
        symptoms=["Connection keeps dropping"], equipment_identifiers=["Site 42"],
        attempted_actions=[act("Restart the affected service", "successful", "M2", "M3")],
        resolution="Restart the affected service rather than rebooting the whole router",
        resolution_status="confirmed_in_conversation",
        applicability_conditions=["Do not reboot the whole router"],
        evidence=[ev("M1", "problem_report"), ev("M2", "suggested_solution"), ev("M3", "confirmed_resolution")],
        confidence=0.9)


async def test_slack_conversation_becomes_searchable_evidence_backed_knowledge(db_session: AsyncSession) -> None:
    await monitor(db_session)
    embedder = FakeEmbedder()
    engine = DiscoveryEngine(session_factory=shared(db_session), gemini_factory=lambda: FakeGemini(slack_responder),
                             embedder_factory=lambda: embedder, debounce_seconds=0.05, max_concurrent_analyses=1)
    ing = SlackIngestor(session_factory=shared(db_session), directory=FakeDirectory(),
                        schedule_analysis=engine.schedule_analysis, bot_user_id=BOT_USER)
    for event in CONVERSATION:
        await ing.handle_payload(envelope(event))
    async with asyncio.timeout(10):
        while engine.queued or engine.analyzing:
            await asyncio.sleep(0.02)

    db_session.expunge_all()
    item = await db_session.scalar(select(KnowledgeItem).where(KnowledgeItem.title.like("Restart the affected%")))
    assert item is not None
    assert item.resolution_status is ResolutionStatus.CONFIRMED_IN_CONVERSATION
    assert item.approval_status.value == "unreviewed"  # never auto-approved
    evidence = list(await db_session.scalars(select(KnowledgeEvidence).where(KnowledgeEvidence.knowledge_item_id == item.id)))
    messages = {m.id: m for m in await thread_messages(db_session)}
    assert {e.message_id for e in evidence} == set(messages)  # evidence = the real Slack messages
    assert all(messages[e.message_id].source_url.startswith("https://test.slack.invalid/") for e in evidence)
    chunk = await db_session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_item_id == item.id))
    assert chunk is not None and chunk.embedding is not None

    found = await hybrid_search(db_session, "Site 42 connection dropping, router reboot", embedder, limit=5,
                                filters=SearchFilters(), min_similarity=0.05, similarity_margin=1.0)
    assert found.ranked and found.ranked[0].item_id == item.id


# ---- API -----------------------------------------------------------------------------------

def configured() -> Settings:
    return Settings(_env_file=None, environment="test", slack_enabled=True,
                    slack_bot_token="xoxb-secret-test", slack_app_token="xapp-secret-test")


async def test_status_reflects_worker_state_and_never_leaks_tokens(api: httpx.AsyncClient, db_session: AsyncSession) -> None:
    app.dependency_overrides[get_settings] = configured
    body = (await api.get("/api/integrations/slack/status")).json()
    assert body["status"] == "worker_not_running" and body["connected"] is False
    assert "xoxb-secret-test" not in str(body) and body["bot_token_configured"] is True

    now = datetime.now(UTC)
    await update_state(db_session, SLACK, status="connected", connected=True, credentials_verified=True,
                       workspace_id=TEAM, workspace_name="Elisa Test Workspace", heartbeat_at=now)
    await db_session.commit()
    body = (await api.get("/api/integrations/slack/status")).json()
    assert body["status"] == "connected" and body["connected"] and body["workspace_name"] == "Elisa Test Workspace"

    await update_state(db_session, SLACK, heartbeat_at=now - timedelta(minutes=5))  # worker died
    await db_session.commit()
    body = (await api.get("/api/integrations/slack/status")).json()
    assert body["status"] == "worker_not_running" and body["connected"] is False

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="test")
    assert (await api.get("/api/integrations/slack/status")).json()["status"] == "disabled"


async def test_channels_listing_and_dev_only_allowlist(api: httpx.AsyncClient, db_session: AsyncSession) -> None:
    app.dependency_overrides[get_slack_client] = lambda: FakeWebClient()
    listing = (await api.get("/api/integrations/slack/channels")).json()
    assert [c["name"] for c in listing["available"]] == ["#noc-test", "#random"] and listing["monitored"] == []

    enabled = await api.post("/api/integrations/slack/channels", json={"channel_id": CHANNEL, "enabled": True})
    assert enabled.status_code == 200 and enabled.json()["monitored"] and enabled.json()["name"] == "#noc-test"
    listing = (await api.get("/api/integrations/slack/channels")).json()
    assert [c["channel_id"] for c in listing["monitored"]] == [CHANNEL]
    assert (await api.post("/api/integrations/slack/channels",
                           json={"channel_id": "bad id", "enabled": True})).status_code == 422
    assert (await api.post("/api/integrations/slack/channels",
                           json={"channel_id": "C0MISSING1", "enabled": True})).status_code == 422

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="production")
    blocked = await api.post("/api/integrations/slack/channels", json={"channel_id": CHANNEL, "enabled": False})
    assert blocked.status_code == 403

    events = (await api.get("/api/integrations/slack/events")).json()
    assert events and events[0]["kind"] == "channel_enabled"


async def test_health_reports_invalid_credentials(api: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_slack_client] = lambda: FakeWebClient(auth_error="invalid_auth")
    body = (await api.get("/api/integrations/slack/health")).json()
    assert body["status"] == "invalid_credentials" and "invalid_auth" in body["detail"]
    app.dependency_overrides[get_slack_client] = lambda: None
    assert (await api.get("/api/integrations/slack/health")).json()["status"] == "not_configured"


# ---- worker --------------------------------------------------------------------------------

@pytest.fixture
def worker_db(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The worker and the test share one session, so every access goes through one lock."""
    factory = shared(db_session)
    monkeypatch.setattr(worker_module, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr("app.services.discovery.factory.get_sessionmaker", lambda: factory)
    return factory


async def state_of(factory):
    async with factory() as s:
        return await get_state(s, SLACK)


async def messages_of(factory):
    async with factory() as s:
        return await thread_messages(s)


async def _run_until(stop: asyncio.Event, coro, predicate, timeout: float = 5) -> None:
    task = asyncio.create_task(coro)
    try:
        async with asyncio.timeout(timeout):
            while not await predicate():
                await asyncio.sleep(0.02)
    finally:
        stop.set()
        await task


async def test_worker_reports_missing_credentials(worker_db) -> None:
    stop = asyncio.Event()
    settings = Settings(_env_file=None, environment="test", slack_enabled=True, slack_bot_token="xoxb-x")

    async def recorded() -> bool:
        state = await state_of(worker_db)
        return state is not None and state.status == "not_configured"

    await _run_until(stop, worker_module.run(settings, stop), recorded)
    state = await state_of(worker_db)
    assert "SLACK_APP_TOKEN" in state.last_error and not state.connected


async def test_worker_reports_invalid_credentials_without_crashing(worker_db) -> None:
    stop = asyncio.Event()

    async def recorded() -> bool:
        state = await state_of(worker_db)
        return state is not None and state.status == "error"

    await _run_until(stop, worker_module.run(configured(), stop,
                                             client_factory=lambda _: FakeWebClient(auth_error="invalid_auth")), recorded)
    state = await state_of(worker_db)
    assert "invalid_auth" in state.last_error and state.credentials_verified is False
    assert "xoxb" not in (state.last_error or "")


class FakeSocket:
    def __init__(self, app_token: str, web_client, auto_reconnect_enabled: bool) -> None:
        self.socket_mode_request_listeners: list = []
        self.acks: list[str] = []
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def is_connected(self) -> bool:
        return self.connected

    async def close(self) -> None:
        self.connected = False

    async def send_socket_mode_response(self, response) -> None:
        self.acks.append(response.envelope_id)


async def test_worker_acks_stores_and_tracks_disconnection(worker_db, monkeypatch: pytest.MonkeyPatch) -> None:
    from slack_sdk.socket_mode.request import SocketModeRequest

    monkeypatch.setattr(worker_module, "HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(worker_module, "WebDirectory", lambda client: FakeDirectory())
    async with worker_db() as s:
        await monitor(s)
    sockets: list[FakeSocket] = []

    def socket_factory(**kwargs):
        sockets.append(FakeSocket(**kwargs))
        return sockets[-1]

    stop = asyncio.Event()
    task = asyncio.create_task(worker_module.run(configured(), stop, client_factory=lambda _: FakeWebClient(),
                                                 socket_factory=socket_factory))
    try:
        async with asyncio.timeout(5):
            while not sockets or not sockets[0].socket_mode_request_listeners or not sockets[0].connected:
                await asyncio.sleep(0.02)
        socket = sockets[0]
        listener = socket.socket_mode_request_listeners[0]
        await listener(socket, SocketModeRequest(type="events_api", envelope_id="env-1", payload=envelope(CONVERSATION[0])))
        assert socket.acks == ["env-1"]  # acknowledged immediately
        async with asyncio.timeout(5):
            while len(await messages_of(worker_db)) < 1:
                await asyncio.sleep(0.02)
        state = await state_of(worker_db)
        assert state.connected and state.credentials_verified and state.workspace_name == "Elisa Test Workspace"
        assert state.last_ingested_at is not None

        socket.connected = False  # connection drops
        async with asyncio.timeout(5):
            while (await state_of(worker_db)).status != "disconnected":
                await asyncio.sleep(0.02)
    finally:
        stop.set()
        await task
    async with worker_db() as s:
        kinds = set(await s.scalars(select(IntegrationEvent.kind)))
    assert {"connected", "message_stored"} <= kinds
