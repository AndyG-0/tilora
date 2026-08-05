"""Discord plugin: recent messages from a configured channel (or thread —
Discord's message-list endpoint treats a thread ID exactly like a channel
ID, so no separate code path is needed to support threads).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import effective_settings, resolve_timezone, settings
from app.plugins.base import Plugin, ToolDef

DISCORD_API_BASE = "https://discord.com/api/v10"

# Discord caps a single messages request at 100.
_MAX_MESSAGE_LIMIT = 100
_SUMMARY_MESSAGE_COUNT = 5


class DiscordPlugin(Plugin):
    id = "discord"
    name = "Discord"
    refresh_interval_seconds = 60

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {settings.discord_bot_token or ''}"}

    @property
    def _channel_id(self) -> str | None:
        return self.config["settings"].get("channel_id")

    @property
    def _message_limit(self) -> int:
        return min(self.config["settings"].get("message_limit", 20), _MAX_MESSAGE_LIMIT)

    @property
    def _time_window_minutes(self) -> int | None:
        return self.config["settings"].get("time_window_minutes")

    @property
    def _display_mode(self) -> str:
        return self.config["settings"].get("display_mode", "static")

    @property
    def _marquee_speed_seconds(self) -> int:
        return self.config["settings"].get("marquee_speed_seconds", 40)

    @property
    def _fade_interval_seconds(self) -> int:
        return self.config["settings"].get("fade_interval_seconds", 6)

    async def _fetch_channel_name(self, client: httpx.AsyncClient) -> str:
        response = await client.get(f"{DISCORD_API_BASE}/channels/{self._channel_id}", headers=self._headers)
        response.raise_for_status()
        return response.json().get("name", "unknown-channel")

    async def _fetch_messages(self, client: httpx.AsyncClient, limit: int) -> list[dict[str, Any]]:
        response = await client.get(
            f"{DISCORD_API_BASE}/channels/{self._channel_id}/messages",
            headers=self._headers,
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def _message_view(self, message: dict[str, Any]) -> dict[str, Any]:
        author = message["author"]
        avatar_url = _avatar_url(author)
        return {
            "id": message["id"],
            "author": author.get("username", "unknown"),
            "avatar_url": avatar_url,
            "content": message.get("content", ""),
            "timestamp": message["timestamp"],
        }

    async def _fetch_raw(self, limit: int) -> tuple[str, list[dict[str, Any]]]:
        async with httpx.AsyncClient(timeout=10) as client:
            channel_name = await self._fetch_channel_name(client)
            raw_messages = await self._fetch_messages(client, limit)

        # Discord returns newest-first; chat logs read oldest -> newest.
        return channel_name, list(reversed(raw_messages))

    async def _fetch(self) -> tuple[str, list[dict[str, Any]]]:
        channel_name, raw_messages = await self._fetch_raw(self._message_limit)

        time_window_minutes = self._time_window_minutes
        if time_window_minutes is not None:
            cutoff = datetime.now(UTC) - timedelta(minutes=time_window_minutes)
            raw_messages = [m for m in raw_messages if datetime.fromisoformat(m["timestamp"]) >= cutoff]

        return channel_name, [self._message_view(m) for m in raw_messages]

    async def _fetch_since(self, cutoff: datetime) -> tuple[str, list[dict[str, Any]]]:
        """Messages at or after `cutoff`, fetched at Discord's max page size.

        Used for "today"/"new" voice queries, which need full day coverage
        rather than the widget's display `message_limit`.
        """
        channel_name, raw_messages = await self._fetch_raw(_MAX_MESSAGE_LIMIT)
        raw_messages = [m for m in raw_messages if datetime.fromisoformat(m["timestamp"]) >= cutoff]
        return channel_name, [self._message_view(m) for m in raw_messages]

    def _payload(self, channel_name: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "channel_name": channel_name,
            "display_mode": self._display_mode,
            "message_limit": self._message_limit,
            "time_window_minutes": self._time_window_minutes,
            "marquee_speed_seconds": self._marquee_speed_seconds,
            "fade_interval_seconds": self._fade_interval_seconds,
            "messages": messages,
        }

    async def get_summary(self) -> dict[str, Any]:
        # A UI-added Discord widget has no channel_id until it's configured
        # separately (dashboard.yaml or a future settings editor) — show an
        # empty channel rather than raising.
        if not self._channel_id:
            return self._payload("", [])
        channel_name, messages = await self._fetch()
        return self._payload(channel_name, messages[-_SUMMARY_MESSAGE_COUNT:])

    async def get_detail(self) -> dict[str, Any]:
        if not self._channel_id:
            return self._payload("", [])
        channel_name, messages = await self._fetch()
        return self._payload(channel_name, messages)

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_recent_discord_messages() -> dict[str, Any]:
            return await self.get_summary()

        async def get_todays_discord_messages() -> dict[str, Any]:
            if not self._channel_id:
                return self._payload("", [])
            tz = resolve_timezone(effective_settings()["timezone"])
            midnight_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
            channel_name, messages = await self._fetch_since(midnight_local.astimezone(UTC))
            return self._payload(channel_name, messages)

        return [
            ToolDef(
                name="get_recent_discord_messages",
                description="Get the most recent messages from the dashboard's configured Discord channel.",
                parameters={"type": "object", "properties": {}},
                handler=get_recent_discord_messages,
            ),
            ToolDef(
                name=f"get_todays_discord_messages_{self.id}",
                description="Get every message posted today (since local midnight) in the dashboard's "
                "configured Discord channel. Use this for requests like 'read my new messages', "
                "'read today's Discord messages', or 'what did I miss on Discord today'.",
                parameters={"type": "object", "properties": {}},
                handler=get_todays_discord_messages,
            ),
        ]


def _avatar_url(author: dict[str, Any]) -> str:
    user_id = author["id"]
    avatar_hash = author.get("avatar")
    if avatar_hash:
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
    default_index = (int(user_id) >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{default_index}.png"
