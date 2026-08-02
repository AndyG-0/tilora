from __future__ import annotations

import httpx
import respx

from app.plugins.bf6.plugin import BF6Plugin
from app.storage.cache import cache

SERVERS_URL = "https://api.gametools.network/bf6/servers/"
STATS_URL = "https://api.gametools.network/bf6/stats/"

SERVERS_RESPONSE = {
    "servers": [
        {
            "serverId": "0007555a-8f2d-4e9c-bf91-62df8d725651",
            "prefix": "The Truth Hurts #2 Hardcore Tsuru Reef",
            "region": "Oceania",
            "currentMap": "Tsuru Reef",
            "mode": "Conquest large",
            "maxPlayers": 64,
            "playerAmount": 24,
            "owner": {"platform": "ps5"},
        }
    ]
}

STATS_RESPONSE = {
    "userName": "levelcap",
    "kills": 314,
    "deaths": 374,
    "killDeath": 0.84,
    "winPercent": "28.0%",
    "accuracy": "20.4%",
    "matchesPlayed": 25,
}


def make_plugin(**settings) -> BF6Plugin:
    return BF6Plugin({"id": "bf6", "settings": {**BF6Plugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin(server_name="", player_name="")

    summary = await plugin.get_summary()

    assert summary["configured"] is False
    assert summary["server"] is None
    assert summary["player"] is None
    assert summary["platform"] == "pc"
    assert "error" not in summary


@respx.mock
async def test_get_summary_with_server_only():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json=SERVERS_RESPONSE))
    plugin = make_plugin(server_name="Tsuru", player_name="")

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["server"]["player_count"] == 24
    assert summary["server"]["max_players"] == 64
    assert summary["server"]["map"] == "Tsuru Reef"
    assert summary["server"]["mode"] == "Conquest large"
    assert summary["player"] is None
    assert "error" not in summary


@respx.mock
async def test_get_summary_with_player_only():
    respx.get(STATS_URL).mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    plugin = make_plugin(server_name="", player_name="LevelCap")

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["server"] is None
    assert summary["player"]["user_name"] == "levelcap"
    assert summary["player"]["kills"] == 314
    assert summary["player"]["kill_death"] == 0.84
    assert "error" not in summary


@respx.mock
async def test_get_summary_with_both_server_and_player():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json=SERVERS_RESPONSE))
    respx.get(STATS_URL).mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    plugin = make_plugin(server_name="Tsuru", player_name="LevelCap")

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["server"]["map"] == "Tsuru Reef"
    assert summary["player"]["user_name"] == "levelcap"
    assert "error" not in summary


@respx.mock
async def test_get_summary_surfaces_server_error_without_raising():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin(server_name="Tsuru", player_name="")

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["server"] is None
    assert "error" in summary


@respx.mock
async def test_get_summary_surfaces_player_error_without_raising():
    respx.get(STATS_URL).mock(return_value=httpx.Response(404, json={"errors": ["Player not found"]}))
    plugin = make_plugin(server_name="", player_name="nonexistent")

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["player"] is None
    assert "error" in summary


@respx.mock
async def test_get_summary_reports_no_server_match_as_error_not_crash():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json={"servers": []}))
    plugin = make_plugin(server_name="zzznonexistentserverxyz123", player_name="")

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["server"] is None
    assert "error" in summary


@respx.mock
async def test_get_summary_combines_both_errors_when_both_fail():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(500))
    respx.get(STATS_URL).mock(return_value=httpx.Response(404, json={"errors": ["Player not found"]}))
    plugin = make_plugin(server_name="Tsuru", player_name="nonexistent")

    summary = await plugin.get_summary()

    assert summary["server"] is None
    assert summary["player"] is None
    assert "error" in summary
    assert "Player not found" in summary["error"]


@respx.mock
async def test_get_detail_matches_summary_shape():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json=SERVERS_RESPONSE))
    respx.get(STATS_URL).mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    plugin = make_plugin(server_name="Tsuru", player_name="LevelCap")

    detail = await plugin.get_detail()

    assert detail["configured"] is True
    assert detail["server"]["map"] == "Tsuru Reef"
    assert detail["player"]["user_name"] == "levelcap"


async def test_get_detail_when_not_configured():
    plugin = make_plugin(server_name="", player_name="")

    detail = await plugin.get_detail()

    assert detail["configured"] is False
    assert detail["server"] is None
    assert detail["player"] is None


@respx.mock
async def test_server_result_is_cached_between_calls():
    route = respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json=SERVERS_RESPONSE))
    plugin = make_plugin(server_name="Tsuru", player_name="")

    await plugin.get_summary()
    await plugin.get_summary()

    assert route.call_count == 1


@respx.mock
async def test_server_error_is_not_cached():
    route = respx.get(SERVERS_URL).mock(side_effect=[httpx.Response(500), httpx.Response(200, json=SERVERS_RESPONSE)])
    plugin = make_plugin(server_name="Tsuru", player_name="")

    first = await plugin.get_summary()
    second = await plugin.get_summary()

    assert "error" in first
    assert "error" not in second
    assert route.call_count == 2


@respx.mock
async def test_player_result_is_cached_between_calls():
    route = respx.get(STATS_URL).mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    plugin = make_plugin(server_name="", player_name="LevelCap")

    await plugin.get_summary()
    await plugin.get_summary()

    assert route.call_count == 1


@respx.mock
async def test_player_error_is_not_cached():
    route = respx.get(STATS_URL).mock(
        side_effect=[
            httpx.Response(404, json={"errors": ["Player not found"]}),
            httpx.Response(200, json=STATS_RESPONSE),
        ]
    )
    plugin = make_plugin(server_name="", player_name="LevelCap")

    first = await plugin.get_summary()
    second = await plugin.get_summary()

    assert "error" in first
    assert "error" not in second
    assert route.call_count == 2


@respx.mock
async def test_cache_is_scoped_by_widget_id_for_multiple_instances():
    route = respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json=SERVERS_RESPONSE))
    plugin_a = BF6Plugin({"id": "bf6", "settings": {**BF6Plugin.default_settings, "server_name": "Tsuru"}})
    plugin_b = BF6Plugin({"id": "bf6-server2", "settings": {**BF6Plugin.default_settings, "server_name": "Tsuru"}})

    await plugin_a.get_summary()
    await plugin_b.get_summary()

    assert route.call_count == 2
    cache._store.clear()


async def test_get_ai_tools_returns_scoped_status_tool():
    plugin = make_plugin(server_name="", player_name="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_bf6_status_bf6"
    result = await tools[0].handler()
    assert result["configured"] is False


async def test_get_ai_tools_name_is_scoped_by_widget_id_for_multiple_instances():
    plugin = BF6Plugin({"id": "bf6-server2", "settings": dict(BF6Plugin.default_settings)})

    tools = plugin.get_ai_tools()

    assert tools[0].name == "get_bf6_status_bf6-server2"
