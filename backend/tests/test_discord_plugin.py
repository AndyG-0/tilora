from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx

from app.plugins.discord.plugin import DISCORD_API_BASE, DiscordPlugin

CHANNEL_ID = "111111111111111111"

CHANNEL_RESPONSE = {"id": CHANNEL_ID, "name": "general"}


def _message(id: str, minutes_ago: int, content: str = "hi") -> dict:
    timestamp = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()
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

    assert len(tools) == 1
    assert tools[0].name == "get_recent_discord_messages"
    result = await tools[0].handler()
    assert result["messages"][0]["id"] == "1"
