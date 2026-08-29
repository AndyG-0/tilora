"""Artificial Analysis plugin: AI language-model leaderboards (coding,
intelligence, cost, speed) from the free-tier artificialanalysis.ai API.

The free tier is rate-limited to 100 requests/day and the underlying
leaderboard data doesn't change meaningfully within a day, so this plugin
fetches at most once every 24 hours regardless of how often the dashboard
polls it: `_fetch()` checks the DB-persisted last fetch's age *before* ever
calling the API, and skips the HTTP call entirely when it's still fresh.
That check is DB-backed (not the in-memory TTLCache) so the 24h window
survives a backend restart. `refresh_interval_seconds` below only paces how
often the dashboard re-polls the (usually already-cached) summary — it is
not the upstream fetch cadence.

On API failure, falls back to the last persisted fetch with `stale: True`
(same shape as nasa_apod's `_fallback_to_last_good`) rather than raising, so
a rate-limit or outage degrades the tile instead of breaking it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from app.config import effective_settings
from app.integrations import artificial_analysis_client
from app.plugins.base import Plugin, ToolDef
from app.storage import db

logger = logging.getLogger(__name__)

# The dataset is identical regardless of how many widget instances exist or
# how each is configured (they only differ in which category they *display*)
# — a single global cache row avoids multiplying upstream calls per instance.
_GLOBAL_FETCH_KEY = "global"

_DAILY_REFRESH = timedelta(hours=24)
_TILE_ITEM_COUNT = 5
_ALLOWED_CATEGORIES = ("coding", "intelligence", "cost", "speed")

# (field to sort by, True = descending/"biggest is best")
_SORT_KEY_BY_CATEGORY: dict[str, tuple[str, bool]] = {
    "coding": ("coding_index", True),
    "intelligence": ("intelligence_index", True),
    "cost": ("blended_price_per_1m", False),  # ascending: cheapest first
    "speed": ("output_tokens_per_second", True),
}


class ArtificialAnalysisPlugin(Plugin):
    id = "artificial_analysis"
    name = "Artificial Analysis"
    refresh_interval_seconds = 1800
    default_settings: ClassVar[dict[str, Any]] = {"category": "coding"}
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    @property
    def category(self) -> str:
        # Defensive fallback since widget settings have no schema layer
        # (same rationale as MoviesPlugin.categories).
        raw = self.config["settings"].get("category", "coding")
        return raw if raw in _ALLOWED_CATEGORIES else "coding"

    def validate_settings(self, payload: dict[str, Any]) -> None:
        category = payload.get("category")
        if category is not None and category not in _ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {_ALLOWED_CATEGORIES}")

    async def _is_configured(self) -> bool:
        return bool((await effective_settings()).get("artificial_analysis_api_key"))

    @staticmethod
    def _should_refetch(last: dict[str, Any] | None) -> bool:
        if last is None:
            return True
        fetched_at = datetime.fromisoformat(last["fetched_at"])
        return datetime.now(UTC) - fetched_at > _DAILY_REFRESH

    async def _persist(self, models: list[dict[str, Any]]) -> None:
        try:
            await asyncio.to_thread(db.record_artificial_analysis_fetch, _GLOBAL_FETCH_KEY, {"models": models})
        except Exception:
            # A DB write failure must never fail a request that already has
            # perfectly good data to show.
            logger.warning("Could not persist Artificial Analysis fetch", exc_info=True)

    async def _fetch(self) -> dict[str, Any] | None:
        """Returns {"models": [...], "fetched_at": iso str, "stale": bool}, or None if never fetched and unavailable."""
        last = await asyncio.to_thread(db.latest_artificial_analysis_fetch, _GLOBAL_FETCH_KEY)
        if not self._should_refetch(last):
            assert last is not None
            return {"models": last["models"], "fetched_at": last["fetched_at"], "stale": False}

        try:
            models = await artificial_analysis_client.get_language_models(
                (await effective_settings()).get("artificial_analysis_api_key")
            )
        except artificial_analysis_client.ArtificialAnalysisError as exc:
            logger.warning("Could not fetch Artificial Analysis leaderboard: %s", exc)
            if last is None:
                return None
            return {"models": last["models"], "fetched_at": last["fetched_at"], "stale": True}

        await self._persist(models)
        return {"models": models, "fetched_at": datetime.now(UTC).isoformat(), "stale": False}

    @staticmethod
    def _ranked(models: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
        sort_key, reverse = _SORT_KEY_BY_CATEGORY[category]
        eligible = [m for m in models if m.get(sort_key) is not None]
        return sorted(eligible, key=lambda m: m[sort_key], reverse=reverse)

    async def get_summary(self) -> dict[str, Any]:
        if not await self._is_configured():
            return {"configured": False, "category": self.category, "models": []}

        fetched = await self._fetch()
        if fetched is None:
            return {"configured": True, "category": self.category, "stale": False, "models": []}

        return {
            "configured": True,
            "category": self.category,
            "stale": fetched["stale"],
            "fetched_at": fetched["fetched_at"],
            "models": self._ranked(fetched["models"], self.category)[:_TILE_ITEM_COUNT],
        }

    async def get_detail(self) -> dict[str, Any]:
        if not await self._is_configured():
            return {"configured": False, "category": self.category, "models": []}

        fetched = await self._fetch()
        if fetched is None:
            return {"configured": True, "category": self.category, "stale": False, "models": []}

        return {
            "configured": True,
            "category": self.category,
            "stale": fetched["stale"],
            "fetched_at": fetched["fetched_at"],
            # Full ranked list (every field, not just the sliced tile view)
            # so the detail view can re-sort by any of the four dimensions
            # client-side without a second fetch.
            "models": self._ranked(fetched["models"], self.category),
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def leaderboard(category: str, limit: int) -> dict[str, Any]:
            if not await self._is_configured():
                return {"models": [], "configured": False}
            fetched = await self._fetch()
            if fetched is None:
                return {"models": [], "configured": True, "as_of": None, "stale": None}
            return {
                "models": self._ranked(fetched["models"], category)[:limit],
                "configured": True,
                "as_of": fetched["fetched_at"],
                "stale": fetched["stale"],
            }

        def _limit_param(description: str) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": description,
                    }
                },
            }

        async def get_best_coding_ai_models(limit: int = _TILE_ITEM_COUNT) -> dict[str, Any]:
            return await leaderboard("coding", limit)

        async def get_smartest_ai_models(limit: int = _TILE_ITEM_COUNT) -> dict[str, Any]:
            return await leaderboard("intelligence", limit)

        async def get_cheapest_ai_models(limit: int = _TILE_ITEM_COUNT) -> dict[str, Any]:
            return await leaderboard("cost", limit)

        async def get_fastest_ai_models(limit: int = _TILE_ITEM_COUNT) -> dict[str, Any]:
            return await leaderboard("speed", limit)

        return [
            ToolDef(
                name="get_best_coding_ai_models",
                description="Get the AI language models currently ranked best for coding tasks, "
                "per Artificial Analysis's Coding Index (free-tier leaderboard, updated at most daily).",
                parameters=_limit_param("How many top models to return (default 5)."),
                handler=get_best_coding_ai_models,
            ),
            ToolDef(
                name="get_smartest_ai_models",
                description="Get the AI language models currently ranked highest for general intelligence, "
                "per Artificial Analysis's Intelligence Index (free-tier leaderboard, updated at most daily).",
                parameters=_limit_param("How many top models to return (default 5)."),
                handler=get_smartest_ai_models,
            ),
            ToolDef(
                name="get_cheapest_ai_models",
                description="Get the AI language models with the lowest blended price per million tokens "
                "(a 3:1 input:output blend approximating typical usage), from Artificial Analysis's free-tier "
                "leaderboard, updated at most daily.",
                parameters=_limit_param("How many top models to return (default 5)."),
                handler=get_cheapest_ai_models,
            ),
            ToolDef(
                name="get_fastest_ai_models",
                description="Get the AI language models with the highest output token throughput "
                "(tokens per second), from Artificial Analysis's free-tier leaderboard, updated at most daily.",
                parameters=_limit_param("How many top models to return (default 5)."),
                handler=get_fastest_ai_models,
            ),
        ]
