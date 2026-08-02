"""2048 puzzle widget: the whole game (board state, moves, best score) runs
client-side in the browser via localStorage — there's no external data or
per-user state for the backend to compute or persist, so this plugin only
supplies the static tile title.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.plugins.base import Plugin


class Game2048Plugin(Plugin):
    id = "game2048"
    name = "2048"
    refresh_interval_seconds = 3600
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 1}

    async def get_summary(self) -> dict[str, Any]:
        return {"title": "2048"}

    async def get_detail(self) -> dict[str, Any]:
        return {"title": "2048"}
