"""Date widget: just tells the frontend which timezone to render in.

Same reasoning as `ClockPlugin` — the calendar date is computed client-side
from the timezone, not polled from the backend every tick. The AI tool below
is the exception, for the same reason as `ClockPlugin`'s: a voice query needs
an actual formatted date back from the backend, not just a timezone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import effective_settings, resolve_timezone
from app.i18n import t
from app.plugins.base import Plugin, ToolDef

_WEEKDAY_KEYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_MONTH_KEYS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)


class DatePlugin(Plugin):
    id = "date"
    name = "Date"
    refresh_interval_seconds = 3600

    async def get_summary(self) -> dict[str, Any]:
        return {"timezone": (await effective_settings())["timezone"]}

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_current_date() -> dict[str, Any]:
            timezone_name = (await effective_settings())["timezone"]
            now = datetime.now(resolve_timezone(timezone_name))
            weekday = t(f"date.weekday.{_WEEKDAY_KEYS[now.weekday()]}", self.locale)
            month = t(f"date.month.{_MONTH_KEYS[now.month - 1]}", self.locale)
            return {"date": f"{weekday}, {month} {now.day}, {now.year}", "timezone": timezone_name}

        return [
            ToolDef(
                name=f"get_current_date_{self.id}",
                description="Get today's calendar date in the dashboard's configured timezone. Use "
                "this for requests like 'what's today's date' or 'what day is it'.",
                parameters={"type": "object", "properties": {}},
                handler=get_current_date,
            )
        ]
