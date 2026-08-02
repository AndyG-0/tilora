"""Static messaging widget: a title/text pair, editable from the UI.

No external data source — settings are the entire payload, following the
same pattern as `dashboard.yaml`-configured, runtime-editable widget
settings (see the weather city / AI prompt editors).
"""

from __future__ import annotations

from typing import Any

from app.plugins.base import Plugin


class MessagePlugin(Plugin):
    id = "message"
    name = "Message"
    refresh_interval_seconds = 300

    async def get_summary(self) -> dict[str, Any]:
        settings = self.config["settings"]
        return {"title": settings.get("title", ""), "text": settings.get("text", "")}

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()
