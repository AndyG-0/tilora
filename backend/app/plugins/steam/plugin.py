"""Steam plugin: the configured Steam user's currently-playing/recently-played
games, their friends' online/in-game status, and recent news for their most-
played games, via Valve's free Steam Web API (see
`app/integrations/steam_client.py`). News fetching/caching lives in
`app/plugins/steam/news.py`.

Both the API key and the user's SteamID64 are secrets/identifiers entered
via the widget's own settings editor (PATCH to the generic widget settings
endpoint) — never committed to dashboard.yaml, same convention as Pi-hole's
password and Jellyfin's API key. `_safe_settings()` masks the key the same
way `PiholePlugin._safe_settings()` does.

get_summary/get_detail degrade gracefully (an "error" string alongside
otherwise-empty data) rather than raising when the Steam Web API rejects the
key or the profile's privacy settings block a call — a real, expected
failure mode (see steam_client's docstring), not a bug.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.integrations import steam_client
from app.plugins.base import Plugin, ToolDef
from app.plugins.steam import news
from app.storage.cache import cache

logger = logging.getLogger(__name__)

# The friends list is the most expensive call (a friend-list fetch plus a
# batched N-steamid player-summaries fetch), and only get_detail needs it —
# cached separately, and briefly, so a quick summary-then-detail tap doesn't
# double the cost, without holding on to a fetched status long enough to go
# noticeably stale for a "who's online right now" widget.
_FRIENDS_CACHE_TTL_SECONDS = 60

_SUMMARY_RECENT_GAMES_COUNT = 3
_DETAIL_RECENT_GAMES_COUNT = 10

# News is fetched for the top few recently-played games, not user-configured
# — see news.py for the per-appid cache/error-isolation that makes this cheap.
_NEWS_GAMES_COUNT = 3
_NEWS_COUNT_PER_GAME = 5
_SUMMARY_NEWS_COUNT = 1
_DETAIL_NEWS_COUNT = 8


def _friends_cache_key(widget_id: str, locale: str) -> str:
    return f"steam_friends:{widget_id}:{locale}"


def _news_games(recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"appid": g["appid"], "name": g["name"]} for g in recent[:_NEWS_GAMES_COUNT]]


class SteamPlugin(Plugin):
    id = "steam"
    name = "Steam"
    refresh_interval_seconds = 60
    default_settings: ClassVar[dict[str, Any]] = {
        "steamid": "",
        "api_key": "",
    }
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    def _settings(self) -> dict[str, Any]:
        return self.config["settings"]

    def _is_configured(self) -> bool:
        return steam_client.is_configured(self._settings())

    def _safe_settings(self) -> dict[str, Any]:
        # api_key is write-only: callers get a boolean "is it set", never the
        # raw value (same pattern as PiholePlugin._safe_settings).
        s = self._settings()
        return {
            "steamid": s.get("steamid", ""),
            "has_api_key": bool(s.get("api_key")),
        }

    async def _player_and_recent(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
        settings = self._settings()
        steamid = settings.get("steamid", "")
        try:
            player = await steam_client.fetch_player_summary(settings, steamid, self.locale)
            recent = await steam_client.fetch_recently_played(settings, steamid)
        except steam_client.SteamError as exc:
            logger.warning("Could not fetch Steam player/recently-played for widget '%s': %s", self.id, exc)
            return None, [], str(exc)
        return player, recent, None

    async def _friends(self) -> tuple[list[dict[str, Any]], str | None]:
        settings = self._settings()
        cache_key = _friends_cache_key(self.id, self.locale)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, None

        try:
            friends = await steam_client.fetch_friends_status(settings, settings.get("steamid", ""), self.locale)
        except steam_client.SteamError as exc:
            # Not cached — a transient failure (or a private friends list
            # the user just fixed) shouldn't lock in an error state for the
            # full TTL window.
            logger.warning("Could not fetch Steam friends status for widget '%s': %s", self.id, exc)
            return [], str(exc)

        cache.set(cache_key, friends, _FRIENDS_CACHE_TTL_SECONDS)
        return friends, None

    @staticmethod
    def _sort_friends(friends: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # In-game first, then online, then everyone else (offline/away/etc),
        # each group alphabetical by name.
        def sort_key(friend: dict[str, Any]) -> tuple[int, str]:
            if friend.get("current_game"):
                rank = 0
            elif friend.get("online"):
                rank = 1
            else:
                rank = 2
            return (rank, (friend.get("name") or "").lower())

        return sorted(friends, key=sort_key)

    async def get_summary(self) -> dict[str, Any]:
        configured = self._is_configured()
        result: dict[str, Any] = {
            "configured": configured,
            "player": None,
            "current_game": None,
            "recent_games": [],
            "news": [],
            **self._safe_settings(),
        }
        if not configured:
            return result

        player, recent, error = await self._player_and_recent()
        result["player"] = player
        result["current_game"] = player["current_game"] if player else None
        result["recent_games"] = recent[:_SUMMARY_RECENT_GAMES_COUNT]

        news_items, news_errors = await news.fetch_news(_news_games(recent), _NEWS_COUNT_PER_GAME, _SUMMARY_NEWS_COUNT)
        result["news"] = news_items
        if news_errors:
            result["news_errors"] = news_errors
        if error:
            result["error"] = error
        return result

    async def get_detail(self) -> dict[str, Any]:
        configured = self._is_configured()
        result: dict[str, Any] = {
            "configured": configured,
            "player": None,
            "current_game": None,
            "recent_games": [],
            "friends": [],
            "news": [],
            **self._safe_settings(),
        }
        if not configured:
            return result

        player, recent, error = await self._player_and_recent()
        friends, friends_error = await self._friends()

        result["player"] = player
        result["current_game"] = player["current_game"] if player else None
        result["recent_games"] = recent[:_DETAIL_RECENT_GAMES_COUNT]
        result["friends"] = self._sort_friends(friends)

        news_items, news_errors = await news.fetch_news(_news_games(recent), _NEWS_COUNT_PER_GAME, _DETAIL_NEWS_COUNT)
        result["news"] = news_items
        if news_errors:
            result["news_errors"] = news_errors

        messages = list(dict.fromkeys(m for m in (error, friends_error) if m))
        if messages:
            result["error"] = " ".join(messages)
        return result

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_steam_status() -> dict[str, Any]:
            return await self.get_summary()

        async def get_steam_news() -> dict[str, Any]:
            if not self._is_configured():
                return {"news": []}
            _, recent, error = await self._player_and_recent()
            if error:
                return {"news": [], "error": error}
            news_items, news_errors = await news.fetch_news(
                _news_games(recent), _NEWS_COUNT_PER_GAME, _DETAIL_NEWS_COUNT
            )
            result: dict[str, Any] = {"news": news_items}
            if news_errors:
                result["news_errors"] = news_errors
            return result

        return [
            ToolDef(
                # Scoped by self.id: like RSS/Sports (and unlike singleton-ish
                # widgets such as Docker/Pi-hole), Steam could plausibly have
                # multiple instances configured for different users.
                name=f"get_steam_status_{self.id}",
                description="Get the configured Steam user's current status: whether they're online, "
                "the game they're currently playing (if any), and recently played games.",
                parameters={"type": "object", "properties": {}},
                handler=get_steam_status,
            ),
            ToolDef(
                name=f"get_steam_news_{self.id}",
                description="Get recent news posts (patch notes, updates, announcements) for the "
                "games this Steam user has recently played. Use for questions like 'what's new for "
                "my games' or 'any updates for X'.",
                parameters={"type": "object", "properties": {}},
                handler=get_steam_news,
            ),
        ]
