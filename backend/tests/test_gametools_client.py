from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import gametools_client

SERVERS_URL = "https://api.gametools.network/bf6/servers/"
STATS_URL = "https://api.gametools.network/bf6/stats/"

# Trimmed but structurally faithful copy of a live gametools.network
# /bf6/servers/ response (sampled from the live API).
SERVERS_RESPONSE = {
    "servers": [
        {
            "serverId": "0007555a-8f2d-4e9c-bf91-62df8d725651",
            "prefix": "The Truth Hurts #2 Hardcore Tsuru Reef, Cairo Bazaar & Golmud",
            "region": "Oceania",
            "regionId": "aws-syd",
            "currentMap": "Tsuru Reef",
            "mode": "Conquest large",
            "smallMode": "CL",
            "maxPlayers": 64,
            "playerAmount": 24,
            "latency": 239,
            "owner": {
                "nucleusId": 2323889005,
                "personaId": 190012498,
                "platformId": 4,
                "platform": "ps5",
            },
        },
        {
            "serverId": "013a4574-34df-4d24-a02f-a34e33464a22",
            "prefix": "HARDCORE BABY -- WE BACK NEW HARCORE ON ROTATION",
            "region": "Oceania",
            "currentMap": "Blackwell Fields",
            "mode": "Conquest large",
            "maxPlayers": 64,
            "playerAmount": 3,
            "owner": {
                "nucleusId": 2798010832,
                "personaId": 1005969110832,
                "platformId": 7,
                "platform": "steam",
            },
        },
    ]
}

# Trimmed but structurally faithful copy of a live gametools.network
# /bf6/stats/ response (sampled from the live API — the real response also
# has weapons/xp/dividedKills/etc arrays this plugin ignores).
STATS_RESPONSE = {
    "userId": "2810309428",
    "avatar": "https://eaassets-a.akamaihd.net/battlelog/defaultavatars/default-avatar-36.png",
    "userName": "levelcap",
    "score": 87585,
    "kills": 314,
    "deaths": 374,
    "wins": 7,
    "loses": 18,
    "assists": 201,
    "killsPerMinute": 0.9,
    "killsPerMatch": 12.56,
    "headShots": 57,
    "winPercent": "28.0%",
    "headshots": "18.15%",
    "killDeath": 0.84,
    "timePlayed": "5:50:06",
    "accuracy": "20.4%",
    "matchesPlayed": 25,
}


def test_is_configured_requires_server_or_player_name():
    assert gametools_client.is_configured({"server_name": "Tsuru"})
    assert gametools_client.is_configured({"player_name": "LevelCap"})
    assert gametools_client.is_configured({"server_name": "Tsuru", "player_name": "LevelCap"})
    assert not gametools_client.is_configured({"server_name": "", "player_name": ""})
    assert not gametools_client.is_configured({})


@respx.mock
async def test_search_servers_returns_normalized_list_sorted_by_population():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json=SERVERS_RESPONSE))

    servers = await gametools_client.search_servers("Tsuru")

    assert len(servers) == 2
    assert servers[0]["name"] == "The Truth Hurts #2 Hardcore Tsuru Reef, Cairo Bazaar & Golmud"
    assert servers[0]["server_id"] == "0007555a-8f2d-4e9c-bf91-62df8d725651"
    assert servers[0]["player_count"] == 24
    assert servers[0]["max_players"] == 64
    assert servers[0]["map"] == "Tsuru Reef"
    assert servers[0]["mode"] == "Conquest large"
    assert servers[0]["region"] == "Oceania"
    # Sorted most-populated first, even though it wasn't first in the response.
    assert servers[1]["player_count"] == 3


@respx.mock
async def test_search_servers_returns_empty_list_when_no_matches():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json={"servers": []}))

    servers = await gametools_client.search_servers("zzznonexistentserverxyz123")

    assert servers == []


async def test_search_servers_raises_without_server_name():
    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.search_servers("")


@respx.mock
async def test_search_servers_raises_on_connect_error():
    respx.get(SERVERS_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.search_servers("Tsuru")


@respx.mock
async def test_search_servers_raises_on_non_json_response():
    respx.get(SERVERS_URL).mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.search_servers("Tsuru")


@respx.mock
async def test_search_servers_degrades_to_empty_list_on_unexpected_shape():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(200, json={"oops": True}))

    servers = await gametools_client.search_servers("Tsuru")

    assert servers == []


@respx.mock
async def test_search_servers_raises_on_server_error_status():
    respx.get(SERVERS_URL).mock(return_value=httpx.Response(502))

    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.search_servers("Tsuru")


@respx.mock
async def test_fetch_player_stats_maps_fields():
    respx.get(STATS_URL).mock(return_value=httpx.Response(200, json=STATS_RESPONSE))

    stats = await gametools_client.fetch_player_stats("LevelCap", "steam")

    assert stats["user_name"] == "levelcap"
    assert stats["kills"] == 314
    assert stats["deaths"] == 374
    assert stats["kill_death"] == 0.84
    assert stats["win_percent"] == "28.0%"
    assert stats["accuracy"] == "20.4%"
    assert stats["headshots"] == "18.15%"
    assert stats["matches_played"] == 25
    assert stats["time_played"] == "5:50:06"


async def test_fetch_player_stats_raises_without_player_name():
    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.fetch_player_stats("", "pc")


@respx.mock
async def test_fetch_player_stats_raises_on_not_found():
    # Confirmed live: an unknown player, or a platform mismatch (e.g.
    # querying a Steam player with platform=pc), returns HTTP 404 with
    # {"errors": ["Player not found"]}.
    respx.get(STATS_URL).mock(return_value=httpx.Response(404, json={"errors": ["Player not found"]}))

    with pytest.raises(gametools_client.GameToolsError, match="Player not found"):
        await gametools_client.fetch_player_stats("nonexistent12345", "pc")


@respx.mock
async def test_fetch_player_stats_raises_on_connect_error():
    respx.get(STATS_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.fetch_player_stats("LevelCap", "steam")


@respx.mock
async def test_fetch_player_stats_raises_on_non_json_response():
    # Confirmed live: gametools.network occasionally returns a plain-text
    # gateway-error body (e.g. "error code: 504") instead of JSON.
    respx.get(STATS_URL).mock(
        return_value=httpx.Response(504, content=b"error code: 504", headers={"content-type": "text/plain"})
    )

    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.fetch_player_stats("LevelCap", "steam")


@respx.mock
async def test_fetch_player_stats_raises_on_non_json_200_response():
    respx.get(STATS_URL).mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(gametools_client.GameToolsError):
        await gametools_client.fetch_player_stats("LevelCap", "steam")


@respx.mock
async def test_fetch_player_stats_defaults_missing_fields():
    respx.get(STATS_URL).mock(return_value=httpx.Response(200, json={"userName": "Sparse"}))

    stats = await gametools_client.fetch_player_stats("Sparse", "pc")

    assert stats["user_name"] == "Sparse"
    assert stats["kills"] == 0
    assert stats["win_percent"] is None
    assert stats["avatar"] is None
