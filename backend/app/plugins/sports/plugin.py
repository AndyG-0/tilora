"""Sports schedule & broadcast plugin: upcoming/today's games (and where to
watch them) for a user-configurable list of `{league, team}` entries, plus a
`trending_leagues`-driven "today's top games" section that surfaces notable
games league-wide regardless of whether the user follows either team (see
`trending.py`) — via ESPN's free public "site API"
(see `app/integrations/espn_client.py`) — no API key, no hardcoded
team/market.

Settings:

    teams:
      - league: nfl
        team: DAL   # ESPN team abbreviation, case-insensitive
    trending_leagues: [nfl, nba, ...]   # leagues fed into "today's top games"

Supported `league` values are ESPN's own sport/league path segments this
plugin knows how to map (see `espn_client.LEAGUE_PATHS`).

Each followed-team entry is fetched (and cached — schedules don't need
per-request freshness) independently, so one misconfigured/unreachable team
surfaces an error for just that entry rather than failing the whole widget.
The trending section is computed independently of followed teams — it's
populated even when no teams are followed.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from app.config import effective_settings
from app.integrations import broadcast_links, espn_client
from app.plugins.base import Plugin, ToolDef
from app.plugins.sports import trending
from app.storage.cache import cache

_CACHE_TTL_SECONDS = 900  # 15 minutes — schedules/broadcasts rarely change minute to minute
_SUMMARY_GAMES_PER_TEAM = 1
_DETAIL_GAMES_PER_TEAM = 5
_SUMMARY_TRENDING_GAMES = 4
_DETAIL_TRENDING_GAMES = 12


def _cache_key(league: str, team: str) -> str:
    return f"sports_schedule:{league}:{team.lower()}"


def _perspective(team_abbr: str, game: dict[str, Any]) -> dict[str, Any]:
    is_home = game["home_abbreviation"].upper() == team_abbr.upper()
    opponent = game["away_team"] if is_home else game["home_team"]
    broadcast_link_list = [{"name": name, "url": broadcast_links.link_for(name)} for name in game["broadcasts"]]
    return {**game, "is_home": is_home, "opponent": opponent, "broadcast_links": broadcast_link_list}


class SportsPlugin(Plugin):
    id = "sports"
    name = "Sports Schedule"
    refresh_interval_seconds = 1800
    default_settings: ClassVar[dict[str, Any]] = {
        "teams": [{"league": "nfl", "team": "DAL"}],
        "trending_leagues": list(espn_client.LEAGUE_PATHS),
    }
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    def _teams(self) -> list[dict[str, Any]]:
        return self.config["settings"].get("teams") or []

    def _is_configured(self) -> bool:
        return bool(self._teams())

    def _trending_leagues(self) -> list[str]:
        return self.config["settings"].get("trending_leagues", list(espn_client.LEAGUE_PATHS))

    async def _fetch_trending(self, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        leagues = self._trending_leagues()
        if not leagues:
            return [], []
        timezone_name = effective_settings()["timezone"]
        return await trending.fetch_trending_games(leagues, timezone_name, limit)

    async def _fetch_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        league = str(entry.get("league", "")).lower()
        team = str(entry.get("team", "") or "")
        league_label = espn_client.LEAGUE_LABELS.get(league, league.upper())

        base = {"league": league, "league_label": league_label, "team": team}

        if not team:
            return {**base, "team_name": "", "games": [], "error": "No team configured."}
        if not espn_client.is_supported_league(league):
            return {**base, "team_name": team, "games": [], "error": f"Unsupported league '{league}'."}

        cache_key = _cache_key(league, team)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = await espn_client.fetch_team_schedule(league, team)
        except espn_client.ESPNError as exc:
            # Not cached — a transient failure shouldn't lock in an error
            # state for the full TTL window.
            return {**base, "team_name": team, "games": [], "error": str(exc)}

        team_name, games = espn_client.parse_team_schedule(data)
        upcoming = sorted((g for g in games if not g["completed"]), key=lambda g: g["date"] or "")

        result = {**base, "team_name": team_name or team, "games": upcoming}
        cache.set(cache_key, result, _CACHE_TTL_SECONDS)
        return result

    async def _fetch_all(self) -> list[dict[str, Any]]:
        return list(await asyncio.gather(*(self._fetch_entry(entry) for entry in self._teams())))

    async def get_summary(self) -> dict[str, Any]:
        configured = self._is_configured()
        games: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        if configured:
            entries = await self._fetch_all()
            for entry in entries:
                if entry.get("error"):
                    errors.append({"league": entry["league"], "team": entry["team"], "error": entry["error"]})
                for game in entry["games"][:_SUMMARY_GAMES_PER_TEAM]:
                    games.append(
                        {
                            "league": entry["league"],
                            "league_label": entry["league_label"],
                            "team": entry["team_name"],
                            **_perspective(entry["team"], game),
                        }
                    )
            games.sort(key=lambda g: g["date"] or "")

        trending_games, trending_errors = await self._fetch_trending(_SUMMARY_TRENDING_GAMES)

        result: dict[str, Any] = {"configured": configured, "games": games, "trending": trending_games}
        if errors:
            result["errors"] = errors
        if trending_errors:
            result["trending_errors"] = trending_errors
        return result

    async def get_detail(self) -> dict[str, Any]:
        configured = self._is_configured()
        teams: list[dict[str, Any]] = []

        if configured:
            entries = await self._fetch_all()
            for entry in entries:
                games = [_perspective(entry["team"], g) for g in entry["games"][:_DETAIL_GAMES_PER_TEAM]]
                team_out: dict[str, Any] = {
                    "league": entry["league"],
                    "league_label": entry["league_label"],
                    "team": entry["team"],
                    "team_name": entry["team_name"],
                    "games": games,
                }
                if entry.get("error"):
                    team_out["error"] = entry["error"]
                teams.append(team_out)

        trending_games, trending_errors = await self._fetch_trending(_DETAIL_TRENDING_GAMES)

        result: dict[str, Any] = {
            "configured": configured,
            "teams": teams,
            "trending": trending_games,
            "trending_leagues": self._trending_leagues(),
        }
        if trending_errors:
            result["trending_errors"] = trending_errors
        return result

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_upcoming_games() -> dict[str, Any]:
            return await self.get_summary()

        async def get_trending_games() -> dict[str, Any]:
            games, errors = await self._fetch_trending(_DETAIL_TRENDING_GAMES)
            result: dict[str, Any] = {"games": games}
            if errors:
                result["errors"] = errors
            return result

        return [
            ToolDef(
                name=f"get_upcoming_games_{self.id}",
                description="Get the next upcoming/in-progress game and broadcast/streaming info for each "
                "team followed by this sports schedule widget.",
                parameters={"type": "object", "properties": {}},
                handler=get_upcoming_games,
            ),
            ToolDef(
                name=f"get_trending_games_{self.id}",
                description="Get today's most notable/popular games (nationally televised and/or "
                "ranked-team matchups) across this widget's tracked leagues, regardless of "
                "whether a specific team is followed.",
                parameters={"type": "object", "properties": {}},
                handler=get_trending_games,
            ),
        ]
