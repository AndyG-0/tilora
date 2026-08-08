"""Today's "trending" games: the most notable games across a set of leagues,
independent of any individual team the user follows.

ESPN's free site API has no real popularity signal, so this ranks games
using two proxies already present in the scoreboard response (see
`espn_client.parse_scoreboard`): a nationally televised broadcast, and (for
college sports) a Top-25 ranked team. Games are fetched per league for a
single explicit calendar day (see `espn_client.fetch_scoreboard`'s docstring
for why the day must be explicit) and merged into one ranked list.

Same per-league error isolation as `plugin.py`'s `_fetch_entry`: one
league's ESPN failure doesn't prevent the others from showing.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.config import resolve_timezone
from app.integrations import broadcast_links, espn_client
from app.storage.cache import cache

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 900  # 15 minutes — matches plugin.py's schedule cache TTL


def _cache_key(league: str, date: str) -> str:
    return f"sports_trending:{league}:{date}"


def _rank_weight(game: dict[str, Any]) -> int:
    if game.get("home_rank") is not None or game.get("away_rank") is not None:
        return 2
    if any(b.get("market") == "national" for b in game.get("broadcasts") or []):
        return 1
    return 0


async def _fetch_league(league: str, date: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not espn_client.is_supported_league(league):
        return [], {"league": league, "error": f"Unsupported league '{league}'."}

    cache_key = _cache_key(league, date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, None

    league_label = espn_client.LEAGUE_LABELS.get(league, league.upper())
    try:
        data = await espn_client.fetch_scoreboard(league, date)
    except espn_client.ESPNError as exc:
        # Not cached — a transient failure shouldn't lock in an error state
        # for the full TTL window.
        logger.warning("Could not fetch trending scoreboard for league '%s': %s", league, exc)
        return [], {"league": league, "error": str(exc)}

    games = [
        {
            **game,
            "league": league,
            "league_label": league_label,
            "home_espn_url": espn_client.team_page_url(league, game["home_abbreviation"]),
            "away_espn_url": espn_client.team_page_url(league, game["away_abbreviation"]),
        }
        for game in espn_client.parse_scoreboard(data)
    ]
    cache.set(cache_key, games, _CACHE_TTL_SECONDS)
    return games, None


async def fetch_trending_games(
    leagues: list[str], timezone_name: str, limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch and rank today's most notable games across `leagues`.

    Returns `(games, errors)` — `games` is the top `limit` entries, most
    notable first (ranked-team / nationally-broadcast games ahead of
    others, chronological within the same weight); `errors` has one entry
    per league that failed to fetch.
    """
    if not leagues:
        return [], []

    tz = resolve_timezone(timezone_name)
    today = datetime.now(tz).strftime("%Y%m%d")

    results = await asyncio.gather(*(_fetch_league(league, today) for league in leagues))

    all_games: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for games, error in results:
        all_games.extend(games)
        if error is not None:
            errors.append(error)

    for game in all_games:
        game["broadcast_links"] = [
            {"name": b["name"], "url": broadcast_links.link_for(b["name"])} for b in game["broadcasts"]
        ]

    all_games.sort(key=lambda g: (-_rank_weight(g), g["date"] or ""))
    return all_games[:limit], errors
