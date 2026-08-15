"""Wordle-style word-guessing widget: the game itself (answer word, guesses)
runs client-side in the browser — only the running stats (games played, wins,
streaks) are state worth persisting, and they follow the household member
around to any device, not just the one they played on, so they're stored as
a "personal"-scope setting (`stats`) via the generic widget-settings endpoint
rather than in browser localStorage.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.plugins.base import Plugin

_DEFAULT_STATS: dict[str, int] = {"played": 0, "won": 0, "currentStreak": 0, "maxStreak": 0}


class WordlePlugin(Plugin):
    id = "wordle"
    name = "Wordle"
    refresh_interval_seconds = 3600
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {"stats": dict(_DEFAULT_STATS)}
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 1}

    async def get_summary(self) -> dict[str, Any]:
        return {"title": "Wordle", "stats": self.config["settings"].get("stats", _DEFAULT_STATS)}

    async def get_detail(self) -> dict[str, Any]:
        return {"title": "Wordle", "stats": self.config["settings"].get("stats", _DEFAULT_STATS)}
