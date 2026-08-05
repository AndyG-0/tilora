"""AI Insights plugin: a scheduled prompt whose result is shown as a widget.

Unlike other plugins, this one doesn't fetch its own data live on each
request — `app.scheduler` runs its prompt on a cron and persists the result
to SQLite. `get_summary`/`get_detail` just read the latest persisted run.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.plugins.base import Plugin
from app.storage import db


class AIInsightsPlugin(Plugin):
    id = "ai-insights"
    name = "AI Insights"
    refresh_interval_seconds = 300
    default_settings = {
        "title": "AI Insights",
        "prompt": "Write a short, friendly good-morning update for the household.",
        "cron": "0 8 * * *",
        "topics": [],
    }

    @property
    def prompt(self) -> str:
        return self.config["settings"]["prompt"]

    @property
    def cron(self) -> str:
        return self.config["settings"]["cron"]

    @property
    def topics(self) -> list[str]:
        # Empty list means "no restriction" — the model gets every plugin's
        # tools, same as before this setting existed.
        return self.config["settings"].get("topics", [])

    async def get_summary(self) -> dict[str, Any]:
        latest = await asyncio.to_thread(db.latest_ai_run, self.id)
        if latest is None:
            return {
                "title": self.config["settings"].get("title", self.name),
                "text": "No briefing generated yet.",
                "ran_at": None,
            }
        return {"title": self.config["settings"].get("title", self.name), **latest}

    async def get_detail(self) -> dict[str, Any]:
        summary = await self.get_summary()
        return {
            **summary,
            "history": await asyncio.to_thread(db.ai_run_history, self.id),
            "prompt": self.prompt,
            "cron": self.cron,
            "topics": self.topics,
        }
