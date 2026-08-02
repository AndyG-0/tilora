"""Clock widget: just tells the frontend which timezone to render in.

The actual ticking happens client-side (`ClockTile.svelte`/`ClockDetail.svelte`
render the current time locally with `Intl.DateTimeFormat`) — polling the
backend once a second for a value that's trivially computable in the browser
would be wasteful and laggy. The only thing that can change here is the
dashboard-wide timezone, so a long refresh interval is fine.
"""

from __future__ import annotations

from typing import Any

from app.config import effective_settings
from app.plugins.base import Plugin


class ClockPlugin(Plugin):
    id = "clock"
    name = "Clock"
    refresh_interval_seconds = 3600

    async def get_summary(self) -> dict[str, Any]:
        return {"timezone": effective_settings()["timezone"]}

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()
