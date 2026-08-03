"""Steam Web API client for the Steam plugin.

Targets Valve's free, key-based Steam Web API (no OAuth — just `?key=...`
query params); a key is generated at https://steamcommunity.com/dev/apikey.
No official Python SDK is used, same thin httpx-client-per-integration
approach as everywhere else in this codebase (see container_client.py,
espn_client.py).

Confirmed by hitting the live endpoints (with an invalid key, since no real
key is available here): Steam returns *HTML*, not JSON, for auth failures —
a bad key gets an HTML "403 Forbidden ... verify your key parameter" body,
and a missing key gets an HTML "400 Bad Request" body. So every response is
status-checked before any attempt to parse it as JSON, and 401/403 get a
specific, actionable error message rather than falling through to the
generic "non-JSON response" case.

Three endpoints are used:
  - ISteamUser/GetPlayerSummaries/v2 — batched, up to ~100 steamids per call
    (used for both the configured user's own profile and their friends'
    profiles).
  - IPlayerService/GetRecentlyPlayedGames/v1 — the configured user's
    recently-played games (last two weeks).
  - ISteamUser/GetFriendList/v1 — the configured user's friend steamids.

GetFriendList and the friends' GetPlayerSummaries calls will also 401/403 if
the configured profile's "Game details"/friends-list privacy isn't set to
Public — a real, expected failure mode (not a bug), surfaced as a
`SteamError` for the plugin to degrade gracefully on, exactly like an
unreachable Pi-hole/Docker host.
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE_URL = "https://api.steampowered.com"

# Steam's documented cap on the number of steamids GetPlayerSummaries
# accepts in one call.
_PLAYER_SUMMARIES_BATCH_SIZE = 100

_PERSONA_STATES = {
    0: "Offline",
    1: "Online",
    2: "Busy",
    3: "Away",
    4: "Snooze",
    5: "Looking to trade",
    6: "Looking to play",
}


class SteamError(Exception):
    """Raised when the Steam Web API can't be reached or rejects a request."""


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("api_key")) and bool(settings.get("steamid"))


async def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{_BASE_URL}{path}", params=params)
        except httpx.HTTPError as exc:
            raise SteamError(f"Could not reach the Steam Web API: {exc}") from exc

    if response.status_code in (401, 403):
        raise SteamError(
            "Steam rejected the request — check the API key, and that the profile's privacy "
            "settings allow it (Game details / friends list must be set to Public)."
        )
    if response.status_code >= 400:
        raise SteamError(f"Steam Web API request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise SteamError(f"Unexpected (non-JSON) response from the Steam Web API: {exc}") from exc
    if not isinstance(data, dict):
        raise SteamError("Unexpected response shape from the Steam Web API.")
    return data


def _player_dict(player: dict[str, Any]) -> dict[str, Any]:
    persona_state = player.get("personastate", 0)
    return {
        "steamid": player.get("steamid", ""),
        "name": player.get("personaname", ""),
        "avatar": player.get("avatarfull", ""),
        "status": _PERSONA_STATES.get(persona_state, "Offline"),
        "online": persona_state != 0,
        "current_game": player.get("gameextrainfo"),
    }


def _game_icon_url(appid: Any, img_icon_url: Any) -> str | None:
    if not appid or not img_icon_url:
        return None
    return f"https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{img_icon_url}.jpg"


def _game_dict(game: dict[str, Any]) -> dict[str, Any]:
    return {
        "appid": game.get("appid"),
        "name": game.get("name", ""),
        "playtime_2weeks_minutes": game.get("playtime_2weeks", 0),
        "playtime_forever_minutes": game.get("playtime_forever", 0),
        "icon_url": _game_icon_url(game.get("appid"), game.get("img_icon_url")),
    }


async def fetch_player_summaries(settings: dict[str, Any], steamids: list[str]) -> list[dict[str, Any]]:
    """Fetch player summaries for up to `_PLAYER_SUMMARIES_BATCH_SIZE` steamids at once.

    Callers with more steamids than that (e.g. `fetch_friends_status` on a
    large friends list) must batch themselves.
    """
    if not steamids:
        return []
    data = await _get(
        "/ISteamUser/GetPlayerSummaries/v2/",
        {"key": settings.get("api_key", ""), "steamids": ",".join(steamids)},
    )
    players = (data.get("response") or {}).get("players")
    if players is None:
        players = []
    if not isinstance(players, list):
        raise SteamError("Unexpected response shape from the Steam Web API.")
    return [_player_dict(p) for p in players if isinstance(p, dict)]


async def fetch_player_summary(settings: dict[str, Any], steamid: str) -> dict[str, Any]:
    """Fetch a single player's summary (the configured user's own profile)."""
    if not steamid:
        raise SteamError("No SteamID64 configured.")
    players = await fetch_player_summaries(settings, [steamid])
    if not players:
        raise SteamError("Steam profile not found — check the configured SteamID64.")
    return players[0]


async def fetch_recently_played(settings: dict[str, Any], steamid: str) -> list[dict[str, Any]]:
    """Fetch the configured user's recently-played games (last two weeks)."""
    if not steamid:
        raise SteamError("No SteamID64 configured.")
    data = await _get(
        "/IPlayerService/GetRecentlyPlayedGames/v1/",
        {"key": settings.get("api_key", ""), "steamid": steamid},
    )
    games = (data.get("response") or {}).get("games")
    if games is None:
        games = []
    if not isinstance(games, list):
        raise SteamError("Unexpected response shape from the Steam Web API.")
    return [_game_dict(g) for g in games if isinstance(g, dict)]


async def fetch_friends_status(settings: dict[str, Any], steamid: str) -> list[dict[str, Any]]:
    """Fetch each of the configured user's friends' online/in-game status.

    Two calls under the hood: the friend list (steamids only), then one or
    more batched GetPlayerSummaries calls for those steamids.
    """
    if not steamid:
        raise SteamError("No SteamID64 configured.")
    data = await _get(
        "/ISteamUser/GetFriendList/v1/",
        {"key": settings.get("api_key", ""), "steamid": steamid, "relationship": "friend"},
    )
    friends = (data.get("friendslist") or {}).get("friends")
    if friends is None:
        friends = []
    if not isinstance(friends, list):
        raise SteamError("Unexpected response shape from the Steam Web API.")

    friend_ids = [f["steamid"] for f in friends if isinstance(f, dict) and f.get("steamid")]
    if not friend_ids:
        return []

    players: list[dict[str, Any]] = []
    for i in range(0, len(friend_ids), _PLAYER_SUMMARIES_BATCH_SIZE):
        batch = friend_ids[i : i + _PLAYER_SUMMARIES_BATCH_SIZE]
        players.extend(await fetch_player_summaries(settings, batch))
    return players
