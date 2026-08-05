"""Wordle-style word-guessing widget: the whole game (answer word, guesses,
win/lose state, stats) runs client-side in the browser via localStorage —
there's no external data or per-user state for the backend to compute or
persist, so this plugin only supplies the static tile title.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.plugins.base import Plugin


class WordlePlugin(Plugin):
    id = "wordle"
    name = "Wordle"
    refresh_interval_seconds = 3600
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 1}

    async def get_summary(self) -> dict[str, Any]:
        return {"title": "Wordle"}

    async def get_detail(self) -> dict[str, Any]:
        return {"title": "Wordle"}
