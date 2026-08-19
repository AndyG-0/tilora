from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app import config
from app.plugins.discord import plugin as discord_plugin_module
from app.plugins.discord.plugin import DISCORD_API_BASE, DiscordPlugin

CHANNEL_ID = "111111111111111111"


@pytest.fixture(autouse=True)
def _set_discord_bot_token(monkeypatch):
    monkeypatch.setattr(config.settings, "discord_bot_token", "test-bot-token")


CHANNEL_RESPONSE = {"id": CHANNEL_ID, "name": "general"}

# Noon UTC, safely away from a day boundary — used by the "today's messages"
# tests below so their pass/fail doesn't depend on how close to real UTC
# midnight the suite happens to run (a `minutes_ago=1` message computed
# against the real wall clock can land on the wrong side of "today" if the
# test runs within a few minutes of actual UTC midnight).
_FIXED_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return _FIXED_NOW.astimezone(tz) if tz else _FIXED_NOW.replace(tzinfo=None)


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr(discord_plugin_module, "datetime", _FrozenDatetime)
    return _FIXED_NOW


def _message(id: str, minutes_ago: int, content: str = "hi", now: datetime | None = None) -> dict:
    timestamp = ((now or datetime.now(UTC)) - timedelta(minutes=minutes_ago)).isoformat()
    return {
        "id": id,
        "content": content,
        "timestamp": timestamp,
        "author": {"id": "222222222222222222", "username": "alice", "avatar": None},
    }


def make_plugin(**settings) -> DiscordPlugin:
    return DiscordPlugin({"id": "discord", "settings": {"channel_id": CHANNEL_ID, **settings}})


def _mock_discord(messages: list[dict]) -> None:
    respx.get(f"{DISCORD_API_BASE}/channels/{CHANNEL_ID}").mock(return_value=httpx.Response(200, json=CHANNEL_RESPONSE))
    respx.get(f"{DISCORD_API_BASE}/channels/{CHANNEL_ID}/messages").mock(
        return_value=httpx.Response(200, json=messages)
    )


@respx.mock
async def test_get_summary_maps_messages_oldest_first():
    # Discord returns newest-first.
    _mock_discord([_message("2", minutes_ago=1), _message("1", minutes_ago=5)])
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["channel_name"] == "general"
    assert summary["display_mode"] == "static"
    assert summary["message_limit"] == 20
    assert summary["time_window_minutes"] is None
    assert [m["id"] for m in summary["messages"]] == ["1", "2"]
    assert summary["messages"][0]["avatar_url"] == (
        f"https://cdn.discordapp.com/embed/avatars/{(int('222222222222222222') >> 22) % 6}.png"
    )


@respx.mock
async def test_get_summary_trims_to_fixed_count():
    messages = [_message(str(i), minutes_ago=i) for i in range(10)]
    _mock_discord(messages)
    plugin = make_plugin(message_limit=10)

    summary = await plugin.get_summary()

    assert len(summary["messages"]) == 5


@respx.mock
async def test_get_detail_uses_full_message_limit():
    messages = [_message(str(i), minutes_ago=i) for i in range(10)]
    _mock_discord(messages)
    plugin = make_plugin(message_limit=10)

    detail = await plugin.get_detail()

    assert len(detail["messages"]) == 10


@respx.mock
async def test_time_window_filters_old_messages():
    _mock_discord([_message("recent", minutes_ago=1), _message("old", minutes_ago=120)])
    plugin = make_plugin(time_window_minutes=60)

    detail = await plugin.get_detail()

    assert [m["id"] for m in detail["messages"]] == ["recent"]


@respx.mock
async def test_avatar_url_uses_custom_avatar_when_present():
    message = _message("1", minutes_ago=0)
    message["author"]["avatar"] = "abc123"
    _mock_discord([message])
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["messages"][0]["avatar_url"] == ("https://cdn.discordapp.com/avatars/222222222222222222/abc123.png")


@respx.mock
async def test_get_ai_tools_exposes_recent_messages_tool():
    _mock_discord([_message("1", minutes_ago=0)])
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert [t.name for t in tools] == ["get_recent_discord_messages", "get_todays_discord_messages_discord"]
    result = await tools[0].handler()
    assert result["messages"][0]["id"] == "1"


@respx.mock
async def test_get_todays_messages_excludes_messages_from_before_midnight(tmp_db, frozen_now):
    # 26 hours before the frozen "now" is always before that day's local
    # midnight.
    _mock_discord(
        [
            _message("today", minutes_ago=1, now=frozen_now),
            _message("yesterday", minutes_ago=26 * 60, now=frozen_now),
        ]
    )
    plugin = make_plugin()

    tools = plugin.get_ai_tools()
    result = await tools[1].handler()

    assert [m["id"] for m in result["messages"]] == ["today"]


@respx.mock
async def test_get_todays_messages_ignores_display_message_limit(tmp_db, frozen_now):
    # message_limit caps the tile's display count, but "today's messages"
    # should still see every message from today regardless of that setting.
    messages = [_message(str(i), minutes_ago=i, now=frozen_now) for i in range(10)]
    _mock_discord(messages)
    plugin = make_plugin(message_limit=3)

    tools = plugin.get_ai_tools()
    result = await tools[1].handler()

    assert len(result["messages"]) == 10


async def test_get_todays_messages_returns_empty_when_no_channel_configured(tmp_db):
    plugin = DiscordPlugin({"id": "discord", "settings": {}})

    tools = plugin.get_ai_tools()
    result = await tools[1].handler()

    assert result["messages"] == []


async def test_unconfigured_discord_plugin_returns_empty_and_not_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "discord_bot_token", None)
    plugin = make_plugin()

    summary = await plugin.get_summary()
    assert summary["configured"] is False
    assert summary["messages"] == []

    detail = await plugin.get_detail()
    assert detail["configured"] is False
    assert detail["messages"] == []


@respx.mock
async def test_discord_plugin_handles_http_errors_gracefully():
    respx.get(f"{DISCORD_API_BASE}/channels/{CHANNEL_ID}").mock(return_value=httpx.Response(401))
    respx.get(f"{DISCORD_API_BASE}/channels/{CHANNEL_ID}/messages").mock(return_value=httpx.Response(500))

    plugin = make_plugin()
    summary = await plugin.get_summary()
    assert summary["configured"] is True
    assert summary["messages"] == []
    assert summary["channel_name"] == "unknown-channel"
