from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import steam_client

SETTINGS = {"api_key": "test-key", "steamid": "76561197960435530"}

PLAYER_SUMMARIES_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
RECENTLY_PLAYED_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
FRIEND_LIST_URL = "https://api.steampowered.com/ISteamUser/GetFriendList/v1/"
NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"

PLAYER_SUMMARIES_RESPONSE = {
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
        "total_count": 1,
        "games": [
            {
                "appid": 220,
                "name": "Half-Life 2",
                "playtime_2weeks": 120,
                "playtime_forever": 4500,
                "img_icon_url": "abcdef1234",
            }
        ],
    }
}

FRIEND_LIST_RESPONSE = {
    "friendslist": {
        "friends": [
            {"steamid": "76561197960265731", "relationship": "friend", "friend_since": 0},
            {"steamid": "76561197960265732", "relationship": "friend", "friend_since": 0},
        ]
    }
}

FRIEND_SUMMARIES_RESPONSE = {
    "response": {
        "players": [
            {
                "steamid": "76561197960265731",
                "personaname": "Alice",
                "avatarfull": "https://example.com/alice.jpg",
                "personastate": 1,
                "gameextrainfo": "Portal 2",
            },
            {
                "steamid": "76561197960265732",
                "personaname": "Bob",
                "avatarfull": "https://example.com/bob.jpg",
                "personastate": 0,
            },
        ]
    }
}

# Confirmed against the live API with an invalid key: Steam returns HTML
# (not JSON) for auth failures.
FORBIDDEN_HTML = (
    "<html><head><title>Forbidden</title></head><body><h1>Forbidden</h1>"
    "Access is denied. Retrying will not help. Please verify your <pre>key=</pre> parameter.</body></html>"
)
BAD_REQUEST_HTML = (
    "<html><head><title>Bad Request</title></head><body><h1>Bad Request</h1>"
    "Required parameter 'key' is missing</body></html>"
)


def test_is_configured_requires_both_key_and_steamid():
    assert steam_client.is_configured(SETTINGS)
    assert not steam_client.is_configured({"api_key": "test-key", "steamid": ""})
    assert not steam_client.is_configured({"api_key": "", "steamid": "76561197960435530"})
    assert not steam_client.is_configured({})


@respx.mock
async def test_fetch_player_summary_maps_fields():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=PLAYER_SUMMARIES_RESPONSE))

    player = await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")

    assert player["name"] == "Robin"
    assert player["status"] == "Online"
    assert player["online"] is True
    assert player["current_game"] == "Half-Life 2"
    assert player["avatar"] == "https://example.com/avatar.jpg"


@respx.mock
async def test_fetch_player_summary_maps_offline_status_without_current_game():
    offline_response = {
        "response": {
            "players": [
                {
                    "steamid": "76561197960435530",
                    "personaname": "Robin",
                    "avatarfull": "https://example.com/avatar.jpg",
                    "personastate": 0,
                }
            ]
        }
    }
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=offline_response))

    player = await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")

    assert player["status"] == "Offline"
    assert player["online"] is False
    assert player["current_game"] is None


@respx.mock
async def test_fetch_player_summary_raises_when_profile_not_found():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json={"response": {"players": []}}))

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")


async def test_fetch_player_summary_raises_without_steamid():
    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_player_summary(SETTINGS, "")


@respx.mock
async def test_fetch_recently_played_maps_fields_and_icon_url():
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json=RECENTLY_PLAYED_RESPONSE))

    games = await steam_client.fetch_recently_played(SETTINGS, "76561197960435530")

    assert len(games) == 1
    assert games[0]["name"] == "Half-Life 2"
    assert games[0]["playtime_2weeks_minutes"] == 120
    assert games[0]["playtime_forever_minutes"] == 4500
    assert games[0]["icon_url"] == (
        "https://media.steampowered.com/steamcommunity/public/images/apps/220/abcdef1234.jpg"
    )


@respx.mock
async def test_fetch_recently_played_returns_empty_list_when_no_games_key():
    respx.get(RECENTLY_PLAYED_URL).mock(return_value=httpx.Response(200, json={"response": {}}))

    games = await steam_client.fetch_recently_played(SETTINGS, "76561197960435530")

    assert games == []


@respx.mock
async def test_fetch_friends_status_batches_friend_list_into_player_summaries():
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=FRIEND_LIST_RESPONSE))
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json=FRIEND_SUMMARIES_RESPONSE))

    friends = await steam_client.fetch_friends_status(SETTINGS, "76561197960435530")

    assert len(friends) == 2
    names = {f["name"] for f in friends}
    assert names == {"Alice", "Bob"}
    alice = next(f for f in friends if f["name"] == "Alice")
    assert alice["current_game"] == "Portal 2"
    bob = next(f for f in friends if f["name"] == "Bob")
    assert bob["online"] is False


@respx.mock
async def test_fetch_friends_status_returns_empty_list_when_no_friends():
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json={"friendslist": {"friends": []}}))

    friends = await steam_client.fetch_friends_status(SETTINGS, "76561197960435530")

    assert friends == []


@respx.mock
async def test_fetch_friends_status_batches_large_friend_lists():
    many_friends = {
        "friendslist": {"friends": [{"steamid": f"765611979{i:08d}", "relationship": "friend"} for i in range(150)]}
    }
    respx.get(FRIEND_LIST_URL).mock(return_value=httpx.Response(200, json=many_friends))

    call_sizes: list[int] = []

    def responder(request: httpx.Request) -> httpx.Response:
        steamids = request.url.params["steamids"].split(",")
        call_sizes.append(len(steamids))
        players = [
            {
                "steamid": sid,
                "personaname": f"Player {sid}",
                "avatarfull": "",
                "personastate": 0,
            }
            for sid in steamids
        ]
        return httpx.Response(200, json={"response": {"players": players}})

    respx.get(PLAYER_SUMMARIES_URL).mock(side_effect=responder)

    friends = await steam_client.fetch_friends_status(SETTINGS, "76561197960435530")

    assert len(friends) == 150
    assert call_sizes == [100, 50]


@respx.mock
async def test_fetch_player_summary_raises_on_forbidden_html_response():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        return_value=httpx.Response(403, content=FORBIDDEN_HTML, headers={"content-type": "text/html"})
    )

    with pytest.raises(steam_client.SteamError, match="rejected the request"):
        await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")


@respx.mock
async def test_fetch_friends_status_raises_on_unauthorized_when_friends_list_private():
    respx.get(FRIEND_LIST_URL).mock(
        return_value=httpx.Response(401, content=FORBIDDEN_HTML, headers={"content-type": "text/html"})
    )

    with pytest.raises(steam_client.SteamError, match="rejected the request"):
        await steam_client.fetch_friends_status(SETTINGS, "76561197960435530")


@respx.mock
async def test_fetch_player_summary_raises_on_bad_request_html_response():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        return_value=httpx.Response(400, content=BAD_REQUEST_HTML, headers={"content-type": "text/html"})
    )

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")


@respx.mock
async def test_fetch_player_summary_raises_on_connect_error():
    respx.get(PLAYER_SUMMARIES_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")


@respx.mock
async def test_fetch_player_summary_raises_on_non_json_200_response():
    respx.get(PLAYER_SUMMARIES_URL).mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")


@respx.mock
async def test_fetch_player_summary_raises_on_unexpected_shape():
    respx.get(PLAYER_SUMMARIES_URL).mock(return_value=httpx.Response(200, json={"oops": True}))

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_player_summary(SETTINGS, "76561197960435530")


async def test_fetch_player_summaries_returns_empty_list_for_no_steamids():
    assert await steam_client.fetch_player_summaries(SETTINGS, []) == []


NEWS_RESPONSE = {
    "appnews": {
        "appid": 220,
        "newsitems": [
            {
                "gid": "123",
                "title": "Half-Life 2: Update Released",
                "url": "https://store.steampowered.com/news/app/220/view/123",
                "author": "Valve",
                "contents": "Fixed some [b]bugs[/b] and <i>issues</i>.",
                "feedlabel": "Half-Life 2 Updates",
                "date": 1700000000,
                "feedname": "steam_updates",
                "feed_type": 0,
                "appid": 220,
                "is_external_url": True,
            }
        ],
        "count": 1,
    }
}


@respx.mock
async def test_fetch_news_for_app_maps_fields():
    respx.get(NEWS_URL).mock(return_value=httpx.Response(200, json=NEWS_RESPONSE))

    news = await steam_client.fetch_news_for_app(220, count=5, maxlength=300)

    assert len(news) == 1
    item = news[0]
    assert item["gid"] == "123"
    assert item["title"] == "Half-Life 2: Update Released"
    assert item["url"] == "https://store.steampowered.com/news/app/220/view/123"
    assert item["author"] == "Valve"
    assert item["feedlabel"] == "Half-Life 2 Updates"
    assert item["date"] == 1700000000
    assert item["is_external_url"] is True
    assert "feedname" not in item
    assert "feed_type" not in item
    assert "appid" not in item


@respx.mock
async def test_fetch_news_for_app_strips_html_and_bbcode_from_contents():
    respx.get(NEWS_URL).mock(return_value=httpx.Response(200, json=NEWS_RESPONSE))

    news = await steam_client.fetch_news_for_app(220, count=5, maxlength=300)

    assert news[0]["contents"] == "Fixed some bugs and issues."


@respx.mock
async def test_fetch_news_for_app_returns_empty_list_when_no_newsitems_key():
    respx.get(NEWS_URL).mock(return_value=httpx.Response(200, json={"appnews": {"appid": 220, "count": 0}}))

    news = await steam_client.fetch_news_for_app(220, count=5, maxlength=300)

    assert news == []


@respx.mock
async def test_fetch_news_for_app_raises_on_unexpected_shape():
    respx.get(NEWS_URL).mock(return_value=httpx.Response(200, json={"appnews": {"newsitems": "oops"}}))

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_news_for_app(220, count=5, maxlength=300)


@respx.mock
async def test_fetch_news_for_app_raises_on_non_json_200_response():
    respx.get(NEWS_URL).mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_news_for_app(220, count=5, maxlength=300)


@respx.mock
async def test_fetch_news_for_app_raises_on_connect_error():
    respx.get(NEWS_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(steam_client.SteamError):
        await steam_client.fetch_news_for_app(220, count=5, maxlength=300)


@respx.mock
async def test_fetch_news_for_app_sends_no_api_key_param():
    route = respx.get(NEWS_URL).mock(return_value=httpx.Response(200, json=NEWS_RESPONSE))

    await steam_client.fetch_news_for_app(220, count=5, maxlength=300)

    request = route.calls[0].request
    assert "key" not in request.url.params
    assert request.url.params["appid"] == "220"
    assert request.url.params["count"] == "5"
    assert request.url.params["maxlength"] == "300"
