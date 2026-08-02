"""Alert plugin: user- or AI-authored alerts with a severity and optional expiry.

Alerts are created either from the UI (`POST /api/alerts`) or by an AI widget
calling the `create_alert` tool this plugin exposes — any AI-insights prompt
can raise one (e.g. "warn if the forecast calls for freezing temperatures").
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.plugins.base import Plugin, ToolDef
from app.storage import db

_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def _severity_key(alert: dict[str, Any]) -> tuple[int, str]:
    return (_SEVERITY_RANK.get(alert["severity"], len(_SEVERITY_RANK)), alert["created_at"])


class AlertPlugin(Plugin):
    id = "alert"
    name = "Alerts"
    refresh_interval_seconds = 60

    async def _active_alerts(self) -> list[dict[str, Any]]:
        alerts = await asyncio.to_thread(db.list_active_alerts, self.id)
        return sorted(alerts, key=_severity_key)

    async def get_summary(self) -> dict[str, Any]:
        alerts = await self._active_alerts()
        return {"count": len(alerts), "most_urgent": alerts[0] if alerts else None}

    async def get_detail(self) -> dict[str, Any]:
        return {"alerts": await self._active_alerts()}

    def get_ai_tools(self) -> list[ToolDef]:
        async def create_alert(
            message: str, severity: str = "info", expires_in_minutes: int | None = None
        ) -> dict[str, Any]:
            return await asyncio.to_thread(db.create_alert, self.id, message, severity, expires_in_minutes)

        return [
            ToolDef(
                name="create_alert",
                description=(
                    "Raise an alert on the dashboard's Alert widget. Use this to surface "
                    "something the person glancing at the dashboard should notice, e.g. an "
                    "unusual weather forecast or an upcoming deadline."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "The alert text to display."},
                        "severity": {
                            "type": "string",
                            "enum": ["info", "warning", "critical"],
                            "description": "How urgent the alert is. Defaults to 'info'.",
                        },
                        "expires_in_minutes": {
                            "type": "integer",
                            "description": "Optional: auto-dismiss the alert after this many minutes.",
                        },
                    },
                    "required": ["message"],
                },
                handler=create_alert,
            )
        ]
