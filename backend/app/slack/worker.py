"""Slack Socket Mode worker (run as its own process: `python -m app.slack.worker`).

- Runs in the `slack-worker` Compose service, separate from the API (no hot reload, so there
  is exactly one listener).
- Verifies the bot token with auth.test before reporting "connected".
- Acknowledges every Socket Mode envelope immediately, then processes events in order from a
  queue: persist message -> schedule the existing debounced Gemini analysis -> embeddings.
- Reconnects automatically (slack-sdk) and records its state in the database for the API.
- Missing configuration or invalid credentials are reported, never crash-looped.
"""

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web.async_client import AsyncWebClient

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiClient
from app.core.config import Settings, get_settings
from app.db.session import dispose_engine, get_sessionmaker
from app.services.discovery.engine import DiscoveryEvent
from app.services.discovery.factory import build_discovery_engine
from app.services.integrations import SLACK, log_event, update_state
from app.slack.channels import set_channel_monitoring
from app.slack.directory import WebDirectory
from app.slack.ingest import SlackIngestor

logger = logging.getLogger("elisa.slack")

HEARTBEAT_SECONDS = 20
RETRY_SECONDS = 60
MIRRORED_KINDS = {"analysis_completed", "analysis_failed", "indexed", "index_pending"}


async def _record(**fields: Any) -> None:
    async with get_sessionmaker()() as session:
        message = fields.pop("event_message", None)
        level = fields.pop("event_level", "info")
        kind = fields.pop("event_kind", "status")
        await update_state(session, SLACK, **fields)
        if message:
            await log_event(session, SLACK, kind, message, level=level)
        await session.commit()


async def verify_credentials(client: AsyncWebClient) -> dict[str, str]:
    """auth.test: raises SlackApiError on invalid tokens. Returns workspace and bot identity."""
    response = await client.auth_test()
    return {"team_id": response["team_id"], "team": response.get("team") or response["team_id"],
            "bot_user_id": response.get("user_id")}


async def bootstrap_channels(client: AsyncWebClient, team_id: str, channel_ids: list[str]) -> None:
    """Enable the channels listed in SLACK_CHANNEL_IDS (explicit allowlist)."""
    if not channel_ids:
        return
    async with get_sessionmaker()() as session:
        for channel_id in channel_ids:
            name = f"#{channel_id}"
            try:
                info = await client.conversations_info(channel=channel_id)
                name = f"#{info['channel']['name']}"
            except SlackApiError as exc:
                logger.warning("conversations.info failed for %s: %s", channel_id, exc.response.get("error"))
            await set_channel_monitoring(session, team_id, channel_id, name, enabled=True)
        await session.commit()


def _mirror(event: DiscoveryEvent) -> None:
    """Copy pipeline results (not message content) into the integration log."""
    if event.kind not in MIRRORED_KINDS:
        return
    title = f"{event.thread_title}: " if event.thread_title else ""

    async def write() -> None:
        try:
            async with get_sessionmaker()() as session:
                await log_event(session, SLACK, event.kind, f"{title}{event.message}", level=event.level,
                                thread_id=event.thread_id)
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Could not record pipeline event")

    asyncio.get_running_loop().create_task(write())


async def run(settings: Settings, stop: asyncio.Event,
              client_factory: Callable[[str], AsyncWebClient] = lambda token: AsyncWebClient(token=token),
              socket_factory: Callable[..., Any] = SocketModeClient) -> None:
    if not settings.slack_enabled:
        await _record(status="disabled", connected=False, credentials_verified=False,
                      connection_mode="socket_mode", last_error=None)
        logger.info("Slack integration disabled (SLACK_ENABLED is not true); idling.")
        await stop.wait()
        return
    if not settings.slack_configured:
        missing = [n for n, v in (("SLACK_BOT_TOKEN", settings.slack_bot_token),
                                  ("SLACK_APP_TOKEN", settings.slack_app_token)) if v is None]
        await _record(status="not_configured", connected=False, credentials_verified=False,
                      connection_mode="socket_mode", last_error=f"Missing {', '.join(missing)}.")
        logger.warning("Slack enabled but not configured: missing %s", ", ".join(missing))
        await stop.wait()
        return

    web = client_factory(settings.slack_bot_token.get_secret_value())
    while not stop.is_set():
        try:
            identity = await verify_credentials(web)
            break
        except SlackApiError as exc:
            code = exc.response.get("error", "unknown_error")
            await _record(status="error", connected=False, credentials_verified=False,
                          last_error=f"Slack rejected the bot token ({code}).", event_kind="auth_failed",
                          event_message=f"Credential check failed: {code}", event_level="error")
            logger.error("Slack auth.test failed: %s; retrying in %ss", code, RETRY_SECONDS)
        except Exception as exc:  # noqa: BLE001 - network problems: retry
            await _record(status="error", connected=False, last_error=f"Could not reach Slack ({type(exc).__name__}).")
            logger.error("Slack unreachable: %s; retrying in %ss", type(exc).__name__, RETRY_SECONDS)
        try:
            await asyncio.wait_for(stop.wait(), timeout=RETRY_SECONDS)
        except TimeoutError:
            pass
    else:
        return

    await bootstrap_channels(web, identity["team_id"], settings.slack_channel_ids)

    gemini = GeminiClient.from_settings(settings)
    engine = build_discovery_engine(settings, gemini, EmbeddingService.from_settings(settings, gemini))
    engine.on_event = _mirror
    ingestor = SlackIngestor(
        session_factory=lambda: get_sessionmaker()(),
        directory=WebDirectory(web),
        schedule_analysis=lambda thread_id, title: engine.schedule_analysis(thread_id, title),
        bot_user_id=identity["bot_user_id"],
    )

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def on_request(client: SocketModeClient, req: SocketModeRequest) -> None:
        # Acknowledge first (Slack expects it within 3 s); expensive work happens later.
        await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        if req.type == "events_api":
            await queue.put(req.payload)

    async def consume() -> None:
        while True:
            payload = await queue.get()
            try:
                result = await ingestor.handle_payload(payload)
                if result.status not in ("ignored",):
                    logger.info("Slack event: %s%s", result.status, f" ({result.reason})" if result.reason else "")
            except Exception as exc:  # noqa: BLE001 - keep consuming; report the failure
                logger.exception("Failed to process Slack event")
                try:
                    await _record(last_error=f"Failed to store an event ({type(exc).__name__}).",
                                  event_kind="ingest_failed", event_level="error",
                                  event_message=f"Failed to store a Slack event ({type(exc).__name__})")
                except Exception:  # noqa: BLE001 - database down: logged above
                    pass
            finally:
                queue.task_done()

    socket = socket_factory(app_token=settings.slack_app_token.get_secret_value(), web_client=web,
                            auto_reconnect_enabled=True)
    socket.socket_mode_request_listeners.append(on_request)

    async def heartbeat() -> None:
        while True:
            connected = bool(await socket.is_connected())
            try:
                await _record(status="connected" if connected else "disconnected", connected=connected,
                              heartbeat_at=datetime.now(UTC))
            except Exception:  # noqa: BLE001
                logger.exception("Heartbeat could not be recorded")
            await asyncio.sleep(HEARTBEAT_SECONDS)

    await _record(status="connecting", connected=False, credentials_verified=True, connection_mode="socket_mode",
                  workspace_id=identity["team_id"], workspace_name=identity["team"],
                  bot_user_id=identity["bot_user_id"], last_error=None)
    tasks: list[asyncio.Task] = []
    try:
        await socket.connect()
        await _record(status="connected", connected=True, heartbeat_at=datetime.now(UTC),
                      event_kind="connected", event_level="success",
                      event_message=f"Connected to Slack workspace {identity['team']} via Socket Mode")
        logger.info("Connected to Slack workspace %s via Socket Mode", identity["team"])
        tasks = [asyncio.create_task(consume()), asyncio.create_task(heartbeat())]
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await engine.shutdown()
        await socket.close()
        try:
            await _record(status="disconnected", connected=False, event_kind="stopped",
                          event_message="Slack worker stopped")
        except Exception:  # noqa: BLE001
            pass


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows
            pass
    try:
        await run(get_settings(), stop)
    finally:
        await dispose_engine()


def entrypoint(runner: Callable[[], Awaitable[None]] = main) -> None:
    asyncio.run(runner())


if __name__ == "__main__":
    entrypoint()
