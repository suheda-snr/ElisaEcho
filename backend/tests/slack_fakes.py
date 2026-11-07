"""Slack test doubles (no network, no real workspace)."""

from typing import Any

from slack_sdk.errors import SlackApiError

TEAM = "T0TEST01"
CHANNEL = "C0TEST01"
OTHER_CHANNEL = "C0TEST02"
BOT_USER = "U0BOT0001"


def envelope(event: dict[str, Any], team: str = TEAM) -> dict[str, Any]:
    return {"team_id": team, "type": "event_callback", "event_id": "Ev1", "event": event}


def message(ts: str, text: str, user: str = "U0ALICE01", thread_ts: str | None = None,
            channel: str = CHANNEL, **extra: Any) -> dict[str, Any]:
    event = {"type": "message", "channel": channel, "channel_type": "channel", "user": user,
             "text": text, "ts": ts, **extra}
    if thread_ts:
        event["thread_ts"] = thread_ts
    return event


def slack_error(code: str) -> SlackApiError:
    return SlackApiError(f"The request to the Slack API failed: {code}", {"ok": False, "error": code})


class FakeDirectory:
    """Names and permalinks as Slack would return them (or None when unknown)."""

    def __init__(self, names: dict[str, str] | None = None) -> None:
        self.names = names or {"U0ALICE01": "Alice (test)", "U0BOB0001": "Bob (test)"}
        self.permalink_calls = 0

    def cached_user_name(self, user_id: str) -> str | None:
        return self.names.get(user_id)

    async def user_name(self, user_id: str) -> str | None:
        return self.names.get(user_id)

    async def permalink(self, channel_id: str, ts: str) -> str | None:
        self.permalink_calls += 1
        return f"https://test.slack.invalid/archives/{channel_id}/p{ts.replace('.', '')}"

    async def thread_title(self, channel_id: str, thread_ts: str) -> str | None:
        return None


class FakeWebClient:
    """Minimal async Slack Web API stand-in."""

    def __init__(self, *, auth_error: str | None = None, channels: list[dict] | None = None) -> None:
        self.auth_error = auth_error
        self.channels = channels or [{"id": CHANNEL, "name": "noc-test", "is_member": True},
                                     {"id": OTHER_CHANNEL, "name": "random", "is_member": False}]

    async def auth_test(self) -> dict:
        if self.auth_error:
            raise slack_error(self.auth_error)
        return {"ok": True, "team_id": TEAM, "team": "Elisa Test Workspace", "user_id": BOT_USER}

    async def conversations_list(self, **_: Any) -> dict:
        return {"ok": True, "channels": self.channels}

    async def conversations_info(self, channel: str) -> dict:
        for c in self.channels:
            if c["id"] == channel:
                return {"ok": True, "channel": c}
        raise slack_error("channel_not_found")
