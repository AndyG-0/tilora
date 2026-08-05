"""Clock widget: just tells the frontend which timezone to render in.

The actual ticking happens client-side (`ClockTile.svelte`/`ClockDetail.svelte`
render the current time locally with `Intl.DateTimeFormat`) — polling the
backend once a second for a value that's trivially computable in the browser
would be wasteful and laggy. The only thing that can change here is the
dashboard-wide timezone, so a long refresh interval is fine.

The AI tool below is the exception: a voice query gets one-shot answered by
the backend (there's no persistent client-side clock ticking in that flow),
so it computes and returns an actual formatted time rather than just a
timezone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from app.config import effective_settings, resolve_timezone
from app.plugins.base import Plugin, ToolDef


class ClockPlugin(Plugin):
    id = "clock"
    name = "Clock"
    refresh_interval_seconds = 3600
    #: "digital" (default), "analog", "binary", "word", or "matrix" — purely
    #: a client-side rendering choice, so the backend just passes it through.
    default_settings: ClassVar[dict[str, Any]] = {"style": "digital"}

    @property
    def _style(self) -> str:
        return self.config["settings"].get("style", "digital")

    async def get_summary(self) -> dict[str, Any]:
        return {"timezone": effective_settings()["timezone"], "style": self._style}

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_current_time() -> dict[str, Any]:
            timezone_name = effective_settings()["timezone"]
            now = datetime.now(resolve_timezone(timezone_name))
            return {"time": now.strftime("%I:%M %p").lstrip("0"), "timezone": timezone_name}

        return [
            ToolDef(
                name=f"get_current_time_{self.id}",
                description="Get the current time in the dashboard's configured timezone. Use this "
                "for requests like 'what time is it' or 'tell me the time'.",
                parameters={"type": "object", "properties": {}},
                handler=get_current_time,
            )
        ]
