from __future__ import annotations

import httpx
import respx

from app.plugins.steam.plugin import SteamPlugin

SETTINGS = {"api_key": "test-key", "steamid": "76561197960435530"}

PLAYER_SUMMARIES_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
RECENTLY_PLAYED_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
FRIEND_LIST_URL = "https://api.steampowered.com/ISteamUser/GetFriendList/v1/"

PLAYER_RESPONSE = {
    "response": {
        "players": [
            {
                "steamid": "76561197960435530",
                "personaname": "Robin",
                "avatarfull": "https://example.com/avatar.jpg",
                "personastate": 1,
                "gameextrainfo": "Half-Life 2",
            }
        ]
    }
}

RECENTLY_PLAYED_RESPONSE = {
    "response": {
        "games": [
            {
                "appid": 220,
                "name": "Half-Life 2",
                "playtime_2weeks": 120,
                "playtime_forever": 4500,
                "img_icon_url": "abc",
            },
            {"appid": 400, "name": "Portal", "playtime_2weeks": 0, "playtime_forever": 300, "img_icon_url": "def"},
        ]
    }
}

FRIEND_LIST_RESPONSE = {
    "friendslist": {
        "friends": [
            {"steamid": "111", "relationship": "friend"},
            {"steamid": "222", "relationship": "friend"},
            {"steamid": "333", "relationship": "friend"},
        ]
    }
}

FRIEND_SUMMARIES_RESPONSE = {
    "response": {
        "players": [
            {
                "steamid": "111",
                "personaname": "Zeb (in-game)",
                "avatarfull": "",
                "personastate": 1,
                "gameextrainfo": "Dota 2",
            },
            {"steamid": "222", "personaname": "Amy (online)", "avatarfull": "", "personastate": 1},
            {"steamid": "333", "personaname": "Cal (offline)", "avatarfull": "", "personastate": 0},
        ]
    }
}


def make_plugin(**settings) -> SteamPlugin:
    return SteamPlugin({"id": "steam", "settings": {**SteamPlugin.default_settings, **settings}})


def _mock_all_endpoints():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=FRIEND_SUMMARIES_RESPONSE if len(request.url.params["steamids"].split(",")) > 1 else PLAYER_RESPONSE,
        )
    )
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))


async def test_get_summary_when_not_configured():
    plugin = make_plugin(steamid="", api_key="")

    summary = await plugin.get_summary()

    assert summary["configured"] is False
    assert summary["player"] is None
    assert summary["current_game"] is None
    assert summary["recent_games"] == []
    assert summary["has_api_key"] is False


async def test_safe_settings_masks_api_key():
    plugin = make_plugin(steamid="76561197960435530", api_key="super-secret")

    summary = await plugin.get_summary()

    assert summary["steamid"] == "76561197960435530"
    assert summary["has_api_key"] is True
    assert "api_key" not in summary
    assert "super-secret" not in str(summary)


@respx.mock
async def test_get_summary_when_configured_reports_player_and_recent_games():
    _mock_all_endpoints()
    plugin = make_plugin(**SETTINGS)

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["player"]["name"] == "Robin"
    assert summary["current_game"] == "Half-Life 2"
    assert len(summary["recent_games"]) == 2
    assert summary["recent_games"][0]["name"] == "Half-Life 2"
    assert "error" not in summary
    assert "friends" not in summary


@respx.mock
async def test_get_summary_surfaces_error_without_raising():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(403))
    plugin = make_plugin(**SETTINGS)

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["player"] is None
    assert summary["recent_games"] == []
    assert "error" in summary


@respx.mock
async def test_get_detail_includes_friends_sorted_ingame_online_offline():
    _mock_all_endpoints()
    plugin = make_plugin(**SETTINGS)

    detail = await plugin.get_detail()

    assert detail["configured"] is True
    assert detail["player"]["name"] == "Robin"
    assert len(detail["recent_games"]) == 2
    names = [f["name"] for f in detail["friends"]]
    assert names == ["Zeb (in-game)", "Amy (online)", "Cal (offline)"]
    assert "error" not in detail


async def test_get_detail_when_not_configured():
    plugin = make_plugin(steamid="", api_key="")

    detail = await plugin.get_detail()

    assert detail["configured"] is False
    assert detail["friends"] == []
    assert detail["recent_games"] == []


@respx.mock
async def test_get_detail_surfaces_friends_error_when_friends_list_private():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=PLAYER_RESPONSE))
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(401))
    plugin = make_plugin(**SETTINGS)

    detail = await plugin.get_detail()

    assert detail["configured"] is True
    assert detail["player"]["name"] == "Robin"
    assert detail["friends"] == []
    assert "error" in detail


@respx.mock
async def test_get_detail_surfaces_player_error_without_raising():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(403))
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json={"friendslist": {"friends": []}}))
    plugin = make_plugin(**SETTINGS)

    detail = await plugin.get_detail()

    assert detail["player"] is None
    assert detail["friends"] == []
    assert "error" in detail


@respx.mock
async def test_friends_list_is_cached_between_detail_calls():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=FRIEND_SUMMARIES_RESPONSE if len(request.url.params["steamids"].split(",")) > 1 else PLAYER_RESPONSE,
        )
    )
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    route = respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))
    plugin = make_plugin(**SETTINGS)

    await plugin.get_detail()
    await plugin.get_detail()

    assert route.call_count == 1


@respx.mock
async def test_friends_error_is_not_cached():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=PLAYER_RESPONSE))
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    route = respx.get(FRIEND_LIST_URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"friendslist": {"friends": []}})]
    )
    plugin = make_plugin(**SETTINGS)

    first = await plugin.get_detail()
    second = await plugin.get_detail()

    assert "error" in first
    assert "error" not in second
    assert route.call_count == 2


async def test_get_ai_tools_returns_scoped_status_tool():
    plugin = make_plugin(steamid="", api_key="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_steam_status_steam"
    result = await tools[0].handler()
    assert result["configured"] is False


async def test_get_ai_tools_name_is_scoped_by_widget_id_for_multiple_instances():
    plugin = SteamPlugin({"id": "steam-alt-user", "settings": dict(SteamPlugin.default_settings)})

    tools = plugin.get_ai_tools()

    assert tools[0].name == "get_steam_status_steam-alt-user"
