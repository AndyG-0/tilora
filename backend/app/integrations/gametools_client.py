"""gametools.network API client for the Battlefield 6 plugin.

Targets the free, unofficial, community-run gametools.network API
(https://api.gametools.network) — a reverse-engineered wrapper around EA's
internal Battlefield services, not an official EA/DICE API. No key, no auth.
Full docs (OpenAPI spec): https://api.gametools.network/openapi.json.

Because it's reverse-engineered, response shapes are inconsistent and can
change without notice (undocumented fields, occasional gateway timeouts
returned as plain-text bodies rather than JSON). Every field access here
uses `.get()` with a default, and unexpected shapes degrade to "no data"
rather than raising — same defensive style as espn_client.py.

Two independent lookups, matching the plugin's two independent settings:
  - `search_servers(server_name)` — GET /bf6/servers/, a fuzzy substring
    search (matched server-side) on server name across all regions.
    Confirmed live to already return everything the widget needs
    (population, map, mode, region) directly, so no second call to the
    per-server detail endpoint (/bf6/detailedserver/) is made — keeps this
    a single request per poll. Sorted most-populated first so the plugin
    can just take the first result as the "best" match for a given name.
  - `fetch_player_stats(player_name, platform)` — GET /bf6/stats/, a
    player's multiplayer stats summary. `platform` must match the platform
    the player's stats are actually tracked under (confirmed live: e.g.
    querying a Steam player with platform=pc returns HTTP 404 "Player not
    found" even though the player exists under platform=steam) — a wrong
    guess here surfaces as "player not found" rather than an error naming
    the actual problem, so the widget's settings expose it as an explicit
    picker rather than a guess.
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE_URL = "https://api.gametools.network"


class GameToolsError(Exception):
    """Raised when the gametools.network API can't be reached or returns something unusable."""


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("server_name")) or bool(settings.get("player_name"))


async def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{_BASE_URL}{path}", params=params)
        except httpx.HTTPError as exc:
            raise GameToolsError(f"Could not reach the gametools.network API: {exc}") from exc

    if response.status_code >= 400:
        message = f"gametools.network request failed (HTTP {response.status_code})."
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            errors = body.get("errors")
            if isinstance(errors, list) and errors:
                message = "; ".join(str(e) for e in errors)
        raise GameToolsError(message)

    try:
        data = response.json()
    except ValueError as exc:
        raise GameToolsError(f"Unexpected (non-JSON) response from gametools.network: {exc}") from exc
    if not isinstance(data, dict):
        raise GameToolsError("Unexpected response shape from gametools.network.")
    return data


def _server_dict(server: dict[str, Any]) -> dict[str, Any]:
    owner = server.get("owner")
    owner_name = owner.get("name") if isinstance(owner, dict) else None
    return {
        "server_id": server.get("serverId", "") or "",
        "name": server.get("prefix", "") or "",
        "region": server.get("region", "") or "",
        "map": server.get("currentMap", "") or "",
        "mode": server.get("mode", "") or "",
        "player_count": server.get("playerAmount", 0) or 0,
        "max_players": server.get("maxPlayers", 0) or 0,
        "owner_name": owner_name if isinstance(owner_name, str) else None,
    }


async def search_servers(server_name: str) -> list[dict[str, Any]]:
    """Search for servers whose name contains `server_name` (a case-insensitive
    substring match, done server-side), across all regions.

    Returns a normalized list, most-populated first. An empty list means no
    matches — not an error. Raises `GameToolsError` on network/parse
    failures.
    """
    if not server_name:
        raise GameToolsError("No server name configured.")

    data = await _get("/bf6/servers/", {"region": "all", "name": server_name})
    servers = data.get("servers")
    if not isinstance(servers, list):
        return []

    parsed = [_server_dict(s) for s in servers if isinstance(s, dict)]
    parsed.sort(key=lambda s: s["player_count"], reverse=True)
    return parsed


def _stats_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_name": data.get("userName", "") or "",
        "avatar": data.get("avatar") or None,
        "score": data.get("score", 0) or 0,
        "kills": data.get("kills", 0) or 0,
        "deaths": data.get("deaths", 0) or 0,
        "wins": data.get("wins", 0) or 0,
        "loses": data.get("loses", 0) or 0,
        "assists": data.get("assists", 0) or 0,
        "kill_death": data.get("killDeath", 0) or 0,
        "win_percent": data.get("winPercent") or None,
        "accuracy": data.get("accuracy") or None,
        "headshots": data.get("headshots") or None,
        "kills_per_minute": data.get("killsPerMinute", 0) or 0,
        "kills_per_match": data.get("killsPerMatch", 0) or 0,
        "time_played": data.get("timePlayed") or None,
        "matches_played": data.get("matchesPlayed", 0) or 0,
    }


async def fetch_player_stats(player_name: str, platform: str) -> dict[str, Any]:
    """Fetch a player's multiplayer stats summary.

    Raises `GameToolsError` if the player/platform combination isn't found
    (gametools.network returns HTTP 404 with `{"errors": [...]}` for this)
    or on any network/parse failure.
    """
    if not player_name:
        raise GameToolsError("No player name configured.")

    data = await _get(
        "/bf6/stats/",
        {"name": player_name, "platform": platform or "pc", "categories": "multiplayer"},
    )
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        raise GameToolsError("; ".join(str(e) for e in errors))
    return _stats_dict(data)
