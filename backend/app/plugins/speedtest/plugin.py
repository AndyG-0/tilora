"""Speedtest plugin: periodic download/upload/ping measurements.

Like AIInsightsPlugin, this doesn't measure anything live on each request —
a full speedtest takes tens of seconds, far too slow for a dashboard poll.
`app.scheduler.run_speedtest_widget` runs it on an interval and persists
each result; `get_summary`/`get_detail` just read what's already recorded.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.plugins.base import Plugin
from app.storage import db

_EMPTY_RUN_FIELDS = {
    "ran_at": None,
    "download_mbps": None,
    "upload_mbps": None,
    "ping_ms": None,
    "server_name": None,
}


class SpeedtestPlugin(Plugin):
    id = "speedtest"
    name = "Speedtest"
    refresh_interval_seconds = 300
    default_settings = {
        "title": "Speedtest",
        "interval_minutes": 60,
    }

    @property
    def interval_minutes(self) -> int:
        return self.config["settings"].get("interval_minutes", 60)

    async def get_summary(self) -> dict[str, Any]:
        title = self.config["settings"].get("title", self.name)
        latest = await asyncio.to_thread(db.latest_speedtest_run, self.id)
        if latest is None:
            return {"title": title, **_EMPTY_RUN_FIELDS}
        return {"title": title, **latest}

    async def get_detail(self) -> dict[str, Any]:
        summary = await self.get_summary()
        return {
            **summary,
            "history": await asyncio.to_thread(db.speedtest_run_history, self.id),
            "interval_minutes": self.interval_minutes,
        }
