"""Slack integration status and configuration.

The Socket Mode connection lives in the slack-worker process; these endpoints read the state
it records and talk to the Slack Web API only for read-only lookups. No token is ever returned.
There is no user authentication yet: changing the channel allowlist is development-only.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from app.api.deps import DbSession, SettingsDep, require_development
from app.core.config import Settings
from app.schemas.integrations import (
    IntegrationEventRead,
    SlackChannel,
    SlackChannelList,
    SlackChannelUpdate,
    SlackHealth,
    SlackStatus,
)
from app.services.integrations import SLACK, get_state, log_event, recent_events
from app.slack.channels import channel_id_of, set_channel_monitoring, slack_sources

router = APIRouter(prefix="/integrations/slack", tags=["integrations"])

HEARTBEAT_STALE_AFTER = timedelta(seconds=90)


def get_slack_client(settings: SettingsDep) -> AsyncWebClient | None:
    """Read-only Web API client for the API process (tests override this dependency)."""
    if settings.slack_bot_token is None:
        return None
    return AsyncWebClient(token=settings.slack_bot_token.get_secret_value())


SlackClientDep = Annotated[AsyncWebClient | None, Depends(get_slack_client)]


def _next_steps(settings: Settings, state_status: str, worker_running: bool) -> list[str]:
    steps = []
    if settings.slack_bot_token is None or settings.slack_app_token is None:
        steps.append("Create the Slack app and set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in backend/.env.")
    if not settings.slack_enabled:
        steps.append("Set SLACK_ENABLED=true in backend/.env.")
    if settings.slack_configured and not worker_running:
        steps.append("Start the worker: docker compose up -d --force-recreate slack-worker")
    if state_status == "error":
        steps.append("Check the tokens: Slack rejected the credentials.")
    return steps


@router.get("/status", response_model=SlackStatus, summary="Slack connection status")
async def slack_status(db: DbSession, settings: SettingsDep) -> SlackStatus:
    state = await get_state(db, SLACK)
    now = datetime.now(UTC)
    worker_running = bool(state and state.heartbeat_at and now - state.heartbeat_at < HEARTBEAT_STALE_AFTER)

    if not settings.slack_enabled:
        effective = "disabled"
    elif not settings.slack_configured:
        effective = "not_configured"
    elif state is None or state.status in ("disabled", "not_configured"):
        effective = "worker_not_running"
    elif state.status == "error":
        effective = "error"
    elif state.status in ("connected", "connecting", "disconnected") and not worker_running:
        effective = "worker_not_running"
    else:
        effective = state.status
    connected = effective == "connected" and bool(state and state.connected and state.credentials_verified)

    sources = await slack_sources(db)
    return SlackStatus(
        enabled=settings.slack_enabled,
        bot_token_configured=settings.slack_bot_token is not None,
        app_token_configured=settings.slack_app_token is not None,
        signing_secret_configured=settings.slack_signing_secret is not None,
        status=effective if effective != "connected" or connected else "disconnected",
        connected=connected,
        credentials_verified=bool(state and state.credentials_verified),
        worker_running=worker_running,
        connection_mode="socket_mode",
        workspace_id=state.workspace_id if state else None,
        workspace_name=state.workspace_name if state else None,
        monitored_channels=[
            SlackChannel(channel_id=channel_id_of(s), name=s.name, monitored=True, source_id=s.id)
            for s in sources if s.enabled
        ],
        last_event_at=state.last_event_at if state else None,
        last_ingested_at=state.last_ingested_at if state else None,
        heartbeat_at=state.heartbeat_at if state else None,
        last_error=state.last_error if state else None,
        next_steps=_next_steps(settings, state.status if state else "", worker_running),
    )


@router.get("/health", response_model=SlackHealth, summary="Live check of the bot token")
async def slack_health(client: SlackClientDep) -> SlackHealth:
    if client is None:
        return SlackHealth(status="not_configured", detail="SLACK_BOT_TOKEN is not set.")
    try:
        response = await client.auth_test()
    except SlackApiError as exc:
        return SlackHealth(status="invalid_credentials", detail=f"Slack error: {exc.response.get('error')}")
    except Exception as exc:  # noqa: BLE001 - network failure
        return SlackHealth(status="unreachable", detail=f"Could not reach Slack ({type(exc).__name__}).")
    return SlackHealth(status="ok", workspace_name=response.get("team"), bot_user_id=response.get("user_id"))


@router.get("/channels", response_model=SlackChannelList, summary="Monitored and available channels")
async def slack_channels(db: DbSession, client: SlackClientDep) -> SlackChannelList:
    sources = await slack_sources(db)
    by_channel = {channel_id_of(s): s for s in sources}
    available: list[SlackChannel] = []
    error = None
    if client is None:
        error = "SLACK_BOT_TOKEN is not set."
    else:
        try:
            response = await client.conversations_list(types="public_channel", exclude_archived=True, limit=200)
            for channel in response.get("channels", []):
                source = by_channel.get(channel["id"])
                available.append(SlackChannel(
                    channel_id=channel["id"], name=f"#{channel['name']}", monitored=bool(source and source.enabled),
                    bot_is_member=bool(channel.get("is_member")), source_id=source.id if source else None,
                ))
        except SlackApiError as exc:
            error = f"Slack error: {exc.response.get('error')}"
        except Exception as exc:  # noqa: BLE001
            error = f"Could not reach Slack ({type(exc).__name__})."
    monitored = [
        SlackChannel(channel_id=cid, name=s.name, monitored=True, source_id=s.id)
        for cid, s in by_channel.items() if s.enabled
    ]
    return SlackChannelList(monitored=monitored, available=available, available_error=error)


@router.post(
    "/channels",
    response_model=SlackChannel,
    summary="Enable or disable monitoring of a channel (development only)",
    dependencies=[Depends(require_development)],
    responses={403: {"description": "Not available outside development"},
               409: {"description": "Workspace not known yet"}},
)
async def update_slack_channel(body: SlackChannelUpdate, db: DbSession, client: SlackClientDep) -> SlackChannel:
    state = await get_state(db, SLACK)
    team_id = state.workspace_id if state else None
    name = f"#{body.channel_id}"
    is_member = None
    if client is not None:
        try:
            if team_id is None:
                team_id = (await client.auth_test())["team_id"]
            info = await client.conversations_info(channel=body.channel_id)
            name = f"#{info['channel']['name']}"
            is_member = bool(info["channel"].get("is_member"))
        except SlackApiError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"Slack could not find this channel ({exc.response.get('error')}).") from None
    if team_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Workspace unknown: configure the Slack tokens first.")
    source = await set_channel_monitoring(db, team_id, body.channel_id, name, enabled=body.enabled)
    await log_event(db, SLACK, "channel_" + ("enabled" if body.enabled else "disabled"),
                    f"Monitoring {'enabled' if body.enabled else 'disabled'} for {name}", channel_id=body.channel_id)
    await db.commit()
    return SlackChannel(channel_id=body.channel_id, name=name, monitored=source.enabled,
                        bot_is_member=is_member, source_id=source.id)


@router.get("/events", response_model=list[IntegrationEventRead], summary="Recent connector events")
async def slack_events(db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[IntegrationEventRead]:
    return [IntegrationEventRead.model_validate(e, from_attributes=True) for e in await recent_events(db, SLACK, limit)]
