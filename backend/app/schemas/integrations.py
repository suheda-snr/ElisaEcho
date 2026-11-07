import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

SlackStatusValue = Literal[
    "disabled", "not_configured", "worker_not_running", "connecting", "connected", "disconnected", "error"
]


class SlackChannel(BaseModel):
    channel_id: str
    name: str
    monitored: bool
    bot_is_member: bool | None = None  # None when unknown (Slack not reachable)
    source_id: uuid.UUID | None = None


class SlackStatus(BaseModel):
    """Never contains tokens; only whether they are configured."""

    enabled: bool
    bot_token_configured: bool
    app_token_configured: bool
    signing_secret_configured: bool
    status: SlackStatusValue
    connected: bool
    credentials_verified: bool
    worker_running: bool
    connection_mode: str
    workspace_id: str | None
    workspace_name: str | None
    monitored_channels: list[SlackChannel]
    last_event_at: datetime | None
    last_ingested_at: datetime | None
    heartbeat_at: datetime | None
    last_error: str | None
    next_steps: list[str]


class SlackChannelList(BaseModel):
    monitored: list[SlackChannel]
    available: list[SlackChannel]
    available_error: str | None = None


class SlackChannelUpdate(BaseModel):
    channel_id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^C[A-Z0-9]{6,20}$")]
    enabled: bool


class SlackHealth(BaseModel):
    status: Literal["ok", "not_configured", "invalid_credentials", "unreachable"]
    workspace_name: str | None = None
    bot_user_id: str | None = None
    detail: str | None = None


class IntegrationEventRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    kind: str
    level: str
    message: str
    channel_id: str | None
    thread_id: uuid.UUID | None
