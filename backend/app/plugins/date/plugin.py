"""Date widget: just tells the frontend which timezone to render in.

Same reasoning as `ClockPlugin` — the calendar date is computed client-side
from the timezone, not polled from the backend every tick.
"""

from __future__ import annotations

from typing import Any

from app.config import effective_settings
from app.plugins.base import Plugin


class DatePlugin(Plugin):
    id = "date"
    name = "Date"
    refresh_interval_seconds = 3600

    async def get_summary(self) -> dict[str, Any]:
        return {"timezone": effective_settings()["timezone"]}

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()
