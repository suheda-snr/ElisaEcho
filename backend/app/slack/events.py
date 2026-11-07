"""Turn raw Slack Events API payloads into normalized message changes (pure, no I/O).

Only plain human messages in public channels are accepted. Bot messages, system subtypes
(joins, topic changes, ...), DMs and empty messages are ignored, which also prevents loops.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

# Subtypes that carry a human message with text.
_MESSAGE_SUBTYPES = {None, "thread_broadcast", "file_share", "me_message"}
_ACCEPTED_CHANNEL_TYPES = {"channel"}  # public channels only (least privilege)

_USER_MENTION = re.compile(r"<@([A-Z0-9]+)(?:\|([^>]+))?>")
_CHANNEL_MENTION = re.compile(r"<#([A-Z0-9]+)(?:\|([^>]*))?>")
_SPECIAL = re.compile(r"<!(here|channel|everyone)(?:\|[^>]*)?>")
_LINK = re.compile(r"<((?:https?|mailto):[^>|]+)(?:\|([^>]+))?>")


@dataclass(frozen=True)
class SlackMessage:
    kind: Literal["new", "edited", "deleted"]
    team_id: str
    channel_id: str
    ts: str  # message id within the channel
    thread_ts: str  # thread key: parent ts (equals ts for a top-level message)
    user_id: str | None
    text: str
    edited_ts: str | None = None

    @property
    def is_reply(self) -> bool:
        return self.thread_ts != self.ts


@dataclass(frozen=True)
class Ignored:
    reason: str


def ts_to_datetime(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


def normalize_text(text: str, user_name: Callable[[str], str | None] = lambda _: None) -> str:
    """Slack mrkdwn -> readable text. Unknown users keep their ID (never invented)."""

    def user(match: re.Match) -> str:
        return "@" + (match.group(2) or user_name(match.group(1)) or match.group(1))

    text = _USER_MENTION.sub(user, text)
    text = _CHANNEL_MENTION.sub(lambda m: "#" + (m.group(2) or m.group(1)), text)
    text = _SPECIAL.sub(lambda m: "@" + m.group(1), text)
    text = _LINK.sub(lambda m: f"{m.group(2)} ({m.group(1)})" if m.group(2) else m.group(1), text)
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return text.strip()


def _is_bot(message: dict[str, Any], bot_user_id: str | None) -> bool:
    return bool(
        message.get("bot_id")
        or message.get("subtype") == "bot_message"
        or (bot_user_id is not None and message.get("user") == bot_user_id)
    )


def parse_event(payload: dict[str, Any], bot_user_id: str | None) -> SlackMessage | Ignored:
    """`payload` is the Events API envelope payload ({"team_id", "event": {...}})."""
    event = payload.get("event") or {}
    team_id = payload.get("team_id") or event.get("team")
    if event.get("type") != "message":
        return Ignored(f"event type {event.get('type')!r}")
    if not team_id or not event.get("channel"):
        return Ignored("missing team or channel")
    if event.get("channel_type", "channel") not in _ACCEPTED_CHANNEL_TYPES:
        return Ignored(f"channel type {event.get('channel_type')!r}")

    subtype = event.get("subtype")
    channel = event["channel"]

    if subtype == "message_deleted":
        previous = event.get("previous_message") or {}
        ts = event.get("deleted_ts") or previous.get("ts")
        if not ts:
            return Ignored("deletion without ts")
        return SlackMessage("deleted", team_id, channel, ts, previous.get("thread_ts") or ts,
                            previous.get("user"), "")

    if subtype == "message_changed":
        message = event.get("message") or {}
        if _is_bot(message, bot_user_id):
            return Ignored("bot message")
        if not message.get("edited"):  # e.g. reply count updates on the parent: not a content edit
            return Ignored("metadata update")
        text = message.get("text") or ""
        if not text.strip():
            return Ignored("empty message")
        ts = message["ts"]
        return SlackMessage("edited", team_id, channel, ts, message.get("thread_ts") or ts,
                            message.get("user"), text, edited_ts=message["edited"].get("ts"))

    if subtype not in _MESSAGE_SUBTYPES:
        return Ignored(f"subtype {subtype!r}")
    if _is_bot(event, bot_user_id):
        return Ignored("bot message")
    text = event.get("text") or ""
    if not text.strip():
        return Ignored("empty message")
    if not event.get("user") or not event.get("ts"):
        return Ignored("missing user or ts")
    ts = event["ts"]
    return SlackMessage("new", team_id, channel, ts, event.get("thread_ts") or ts, event["user"], text)


def source_external_id(team_id: str, channel_id: str) -> str:
    return f"{team_id}:{channel_id}"


def thread_external_id(channel_id: str, thread_ts: str) -> str:
    return f"{channel_id}:{thread_ts}"
