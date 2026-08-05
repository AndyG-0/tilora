from __future__ import annotations

import httpx
import respx

from app.plugins.steam.plugin import SteamPlugin

SETTINGS = {"api_key": "test-key", "steamid": "76561197960435530"}

PLAYER_SUMMARIES_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
RECENTLY_PLAYED_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
FRIEND_LIST_URL = "https://api.steampowered.com/ISteamUser/GetFriendList/v1/"
NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"

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


NEWS_RESPONSES = {
    220: {
        "appnews": {
            "appid": 220,
            "newsitems": [
                {
                    "gid": "1",
                    "title": "Half-Life 2 Update",
                    "url": "https://example.com/news/1",
                    "author": "Valve",
                    "contents": "",
                    "feedlabel": "Updates",
                    "date": 1700000000,
                    "feedname": "x",
                    "feed_type": 0,
                    "appid": 220,
                    "is_external_url": True,
                }
            ],
            "count": 1,
        }
    },
    400: {
        "appnews": {
            "appid": 400,
            "newsitems": [
                {
                    "gid": "2",
                    "title": "Portal Update",
                    "url": "https://example.com/news/2",
                    "author": "Valve",
                    "contents": "",
                    "feedlabel": "Updates",
                    "date": 1700000100,
                    "feedname": "x",
                    "feed_type": 0,
                    "appid": 400,
                    "is_external_url": True,
                }
            ],
            "count": 1,
        }
    },
}


def _news_responder(request: httpx.Request) -> httpx.Response:
    appid = int(request.url.params["appid"])
    return httpx.Response(200, json=NEWS_RESPONSES.get(appid, {"appnews": {"newsitems": []}}))


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
    respx.get(NEWS_URL).mock(side_effect=_news_responder)


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
async def test_get_summary_includes_single_latest_news_item():
    _mock_all_endpoints()
    plugin = make_plugin(**SETTINGS)

    summary = await plugin.get_summary()

    assert len(summary["news"]) == 1
    assert summary["news"][0]["title"] == "Portal Update"
    assert "news_errors" not in summary


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


@respx.mock
async def test_get_detail_includes_news_for_all_recent_games():
    _mock_all_endpoints()
    plugin = make_plugin(**SETTINGS)

    detail = await plugin.get_detail()

    assert [item["title"] for item in detail["news"]] == ["Portal Update", "Half-Life 2 Update"]
    assert "news_errors" not in detail


@respx.mock
async def test_get_detail_isolates_news_error_per_game():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=FRIEND_SUMMARIES_RESPONSE if len(request.url.params["steamids"].split(",")) > 1 else PLAYER_RESPONSE,
        )
    )
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))

    def failing_news_responder(request: httpx.Request) -> httpx.Response:
        if int(request.url.params["appid"]) == 220:
            return httpx.Response(500)
        return _news_responder(request)

    respx.get(NEWS_URL).mock(side_effect=failing_news_responder)
    plugin = make_plugin(**SETTINGS)

    detail = await plugin.get_detail()

    assert [item["title"] for item in detail["news"]] == ["Portal Update"]
    assert len(detail["news_errors"]) == 1
    assert detail["news_errors"][0]["appid"] == 220
    assert detail["news_errors"][0]["game_name"] == "Half-Life 2"


@respx.mock
async def test_news_is_cached_across_summary_and_detail_calls():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=FRIEND_SUMMARIES_RESPONSE if len(request.url.params["steamids"].split(",")) > 1 else PLAYER_RESPONSE,
        )
    )
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))
    route = respx.get(NEWS_URL).mock(side_effect=_news_responder)
    plugin = make_plugin(**SETTINGS)

    await plugin.get_summary()
    await plugin.get_detail()

    assert route.call_count == 2


@respx.mock
async def test_news_error_is_not_cached_at_plugin_level():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=PLAYER_RESPONSE))
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))
    route = respx.get(NEWS_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json=NEWS_RESPONSES[220]),
            httpx.Response(200, json=NEWS_RESPONSES[400]),
        ]
    )
    plugin = make_plugin(**SETTINGS)

    first = await plugin.get_summary()
    second = await plugin.get_summary()

    assert "news_errors" in first
    assert "news_errors" not in second
    assert route.call_count == 4


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
    respx.get(NEWS_URL).mock(side_effect=_news_responder)
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
    respx.get(NEWS_URL).mock(side_effect=_news_responder)
    route = respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))
    plugin = make_plugin(**SETTINGS)

    await plugin.get_detail()
    await plugin.get_detail()

    assert route.call_count == 1


@respx.mock
async def test_friends_error_is_not_cached():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=PLAYER_RESPONSE))
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))
    respx.get(NEWS_URL).mock(side_effect=_news_responder)
    route = respx.get(FRIEND_LIST_URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"friendslist": {"friends": []}})]
    )
    plugin = make_plugin(**SETTINGS)

    first = await plugin.get_detail()
    second = await plugin.get_detail()

    assert "error" in first
    assert "error" not in second
    assert route.call_count == 2


async def test_get_ai_tools_returns_scoped_status_and_news_tools():
    plugin = make_plugin(steamid="", api_key="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 2
    assert tools[0].name == "get_steam_status_steam"
    assert tools[1].name == "get_steam_news_steam"
    result = await tools[0].handler()
    assert result["configured"] is False
    news_result = await tools[1].handler()
    assert news_result["news"] == []


async def test_get_ai_tools_name_is_scoped_by_widget_id_for_multiple_instances():
    plugin = SteamPlugin({"id": "steam-alt-user", "settings": dict(SteamPlugin.default_settings)})

    tools = plugin.get_ai_tools()

    assert tools[0].name == "get_steam_status_steam-alt-user"
    assert tools[1].name == "get_steam_news_steam-alt-user"


@respx.mock
async def test_get_steam_news_tool_returns_merged_news_for_recent_games():
    _mock_all_endpoints()
    plugin = make_plugin(**SETTINGS)

    tools = plugin.get_ai_tools()
    news_tool = next(t for t in tools if t.name == "get_steam_news_steam")
    result = await news_tool.handler()

    assert [item["title"] for item in result["news"]] == ["Portal Update", "Half-Life 2 Update"]
    assert "news_errors" not in result
