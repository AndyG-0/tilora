"""Steam news for the games the configured user has recently played.

Same per-item error isolation as `sports/trending.py`'s per-league fetch:
one game's Steam Web API failure doesn't prevent the others' news from
showing. Cached per appid rather than per widget, since a game's news is the
same regardless of which Steam widget instance asked for it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.integrations import steam_client
from app.storage.cache import cache

logger = logging.getLogger(__name__)

# News posts publish at most a few times a day even for popular titles, far
# less volatile than presence/friends data — a longer TTL than the 60s
# friends cache is fine, and it caps worst-case load on Valve's endpoint
# from the AI-tool path, which bypasses widgets.py's outer response cache.
_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _cache_key(appid: int) -> str:
    return f"steam_news:{appid}"


async def _fetch_one(appid: int, game_name: str, count: int) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    cache_key = _cache_key(appid)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, None

    try:
        items = await steam_client.fetch_news_for_app(appid, count=count, maxlength=300)
    except steam_client.SteamError as exc:
        # Not cached — a transient failure shouldn't lock in an error state
        # for the full TTL window.
        logger.warning("Could not fetch Steam news for appid %s: %s", appid, exc)
        return [], {"appid": appid, "game_name": game_name, "error": str(exc)}

    tagged = [{**item, "appid": appid, "game_name": game_name} for item in items]
    cache.set(cache_key, tagged, _CACHE_TTL_SECONDS)
    return tagged, None


async def fetch_news(
    games: list[dict[str, Any]], count_per_game: int, limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch and merge recent news across `games` (`[{"appid", "name"}, ...]`).

    Returns `(items, errors)` — `items` is the top `limit` entries across all
    games, newest first; `errors` has one entry per game whose news fetch
    failed.
    """
    if not games:
        return [], []

    results = await asyncio.gather(*(_fetch_one(g["appid"], g["name"], count_per_game) for g in games))

    all_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for items, error in results:
        all_items.extend(items)
        if error is not None:
            errors.append(error)

    all_items.sort(key=lambda i: i["date"], reverse=True)
    return all_items[:limit], errors
