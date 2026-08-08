"""Battlefield 6 server/stats plugin: a user-configured BF6 server's live
population/current map, plus (optionally) a configured player's stats
summary, via the free, unofficial, community-run gametools.network API (see
`app/integrations/gametools_client.py`) — no API key, no auth.

Settings hold `server_name`, `player_name`, and `platform`, each optional
and independent — a user might track just a server, just a player, or both.
`server_name` is matched via a fuzzy substring search on every poll (see
`gametools_client.search_servers`) rather than a stored server id, since
this is a low-traffic personal dashboard and re-searching is cheap; the
most-populated match is used. `platform` only affects the player stats
lookup — gametools.network requires it to match the platform the player's
stats are actually tracked under (ea/xbox/psn/steam/epic/pc/etc), so a
wrong guess here surfaces as "player not found" rather than a hard error.

get_summary()/get_detail() never raise — each of the (independent)
server/player lookups degrades to an "error" string on failure, same
"don't cache errors" convention as Sports/Steam. There's no extra data the
detail view needs beyond the summary (unlike Steam's friends list), so both
share one fetch path.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar

from app.i18n import t
from app.integrations import gametools_client
from app.plugins.base import Plugin, ToolDef
from app.storage.cache import cache

logger = logging.getLogger(__name__)

# Server population/current map change fast — short TTL, matching the
# plugin's own 60s refresh interval (same cadence as Steam's presence data).
_CACHE_TTL_SECONDS = 60


def _server_cache_key(widget_id: str, server_name: str) -> str:
    return f"bf6_server:{widget_id}:{server_name.lower()}"


def _player_cache_key(widget_id: str, player_name: str, platform: str) -> str:
    return f"bf6_player:{widget_id}:{player_name.lower()}:{platform.lower()}"


class BF6Plugin(Plugin):
    id = "bf6"
    name = "Battlefield 6"
    refresh_interval_seconds = 60
    default_settings: ClassVar[dict[str, Any]] = {
        "server_name": "",
        "player_name": "",
        "platform": "pc",
    }
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    def _settings(self) -> dict[str, Any]:
        return self.config["settings"]

    def _server_name(self) -> str:
        return str(self._settings().get("server_name") or "")

    def _player_name(self) -> str:
        return str(self._settings().get("player_name") or "")

    def _platform(self) -> str:
        return str(self._settings().get("platform") or "pc")

    def _is_configured(self) -> bool:
        return gametools_client.is_configured(self._settings())

    async def _fetch_server(self) -> tuple[dict[str, Any] | None, str | None]:
        server_name = self._server_name()
        if not server_name:
            return None, None

        cache_key = _server_cache_key(self.id, server_name)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, None

        try:
            servers = await gametools_client.search_servers(server_name)
        except gametools_client.GameToolsError as exc:
            # Not cached — a transient failure shouldn't lock in an error
            # state for the full TTL window.
            logger.warning("Could not search BF6 servers matching '%s': %s", server_name, exc)
            return None, str(exc)

        if not servers:
            return None, t("bf6.error.server_not_found", self.locale, server_name=server_name)

        server = servers[0]
        cache.set(cache_key, server, _CACHE_TTL_SECONDS)
        return server, None

    async def _fetch_player(self) -> tuple[dict[str, Any] | None, str | None]:
        player_name = self._player_name()
        if not player_name:
            return None, None

        platform = self._platform()
        cache_key = _player_cache_key(self.id, player_name, platform)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, None

        try:
            stats = await gametools_client.fetch_player_stats(player_name, platform)
        except gametools_client.GameToolsError as exc:
            logger.warning("Could not fetch BF6 player stats for '%s': %s", player_name, exc)
            return None, str(exc)

        cache.set(cache_key, stats, _CACHE_TTL_SECONDS)
        return stats, None

    async def _fetch_all(self) -> dict[str, Any]:
        (server_data, server_error), (player_data, player_error) = await asyncio.gather(
            self._fetch_server(), self._fetch_player()
        )

        result: dict[str, Any] = {
            "configured": True,
            "server": server_data,
            "player": player_data,
            "server_name": self._server_name(),
            "player_name": self._player_name(),
            "platform": self._platform(),
        }
        errors = [e for e in (server_error, player_error) if e]
        if errors:
            result["error"] = " ".join(errors)
        return result

    async def get_summary(self) -> dict[str, Any]:
        if not self._is_configured():
            return {
                "configured": False,
                "server": None,
                "player": None,
                "server_name": self._server_name(),
                "player_name": self._player_name(),
                "platform": self._platform(),
            }
        return await self._fetch_all()

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_bf6_status() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                # Scoped by self.id: like RSS/Sports/Steam, BF6 could
                # plausibly have multiple instances configured (e.g. tracking
                # different servers or players at once).
                name=f"get_bf6_status_{self.id}",
                description="Get the configured Battlefield 6 server's live population/current map "
                "and/or the configured player's multiplayer stats summary (kills, deaths, K/D, win "
                "percent, accuracy).",
                parameters={"type": "object", "properties": {}},
                handler=get_bf6_status,
            )
        ]
