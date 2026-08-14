"""2048 puzzle widget: the game itself (board state, moves) runs client-side
in the browser — only the best score is state worth persisting, and it
follows the household member around to any device, not just the one they set
it on, so it's stored as a "personal"-scope setting (`best_score`) via the
generic widget-settings endpoint rather than in browser localStorage.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.plugins.base import Plugin


class Game2048Plugin(Plugin):
    id = "game2048"
    name = "2048"
    refresh_interval_seconds = 3600
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {"best_score": 0}
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 1}

    async def get_summary(self) -> dict[str, Any]:
        return {"title": "2048", "best_score": self.config["settings"].get("best_score", 0)}

    async def get_detail(self) -> dict[str, Any]:
        return {"title": "2048", "best_score": self.config["settings"].get("best_score", 0)}
