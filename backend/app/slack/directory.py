"""Slack Web API lookups with small caches. Failures return None; nothing is invented."""

import logging

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from app.slack.events import normalize_text

logger = logging.getLogger(__name__)


class WebDirectory:
    def __init__(self, client: AsyncWebClient) -> None:
        self.client = client
        self._users: dict[str, str | None] = {}
        self._titles: dict[tuple[str, str], str | None] = {}

    def cached_user_name(self, user_id: str) -> str | None:
        return self._users.get(user_id)

    async def user_name(self, user_id: str) -> str | None:
        if user_id not in self._users:
            try:
                response = await self.client.users_info(user=user_id)  # needs users:read
                user = response["user"]
                profile = user.get("profile") or {}
                self._users[user_id] = profile.get("display_name") or profile.get("real_name") or user.get("name")
            except SlackApiError as exc:
                logger.warning("users.info failed: %s", exc.response.get("error"))
                self._users[user_id] = None
        return self._users[user_id]

    async def permalink(self, channel_id: str, ts: str) -> str | None:
        try:
            response = await self.client.chat_getPermalink(channel=channel_id, message_ts=ts)
            return response.get("permalink")
        except SlackApiError as exc:
            logger.warning("chat.getPermalink failed: %s", exc.response.get("error"))
            return None

    async def thread_title(self, channel_id: str, thread_ts: str) -> str | None:
        """Title from the thread's parent message (best effort, needs channels:history)."""
        key = (channel_id, thread_ts)
        if key not in self._titles:
            try:
                response = await self.client.conversations_replies(channel=channel_id, ts=thread_ts, limit=1)
                messages = response.get("messages") or []
                text = normalize_text(messages[0].get("text", ""), self.cached_user_name) if messages else ""
                first = text.splitlines()[0] if text else ""
                self._titles[key] = (first[:120] + ("…" if len(first) > 120 else "")) or None
            except SlackApiError as exc:
                logger.warning("conversations.replies failed: %s", exc.response.get("error"))
                self._titles[key] = None
        return self._titles[key]
