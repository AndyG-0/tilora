"""Packages plugin: a per-user delivery tracker backed by 17Track.

`"personal"`-scope: each household member tracks their own deliveries, not
one shared household list — see the `packages` table comment in
`app.storage.db`. Adding/removing a tracking number goes through
`app.api.packages` (register with 17Track, then insert a row scoped to the
requesting user); status/ETA refreshes happen out-of-band via
`app.scheduler`'s periodic job (which refreshes every user's packages for
the widget, not just the current viewer's), not on every dashboard poll —
17Track's free tier is rate-limited, so get_summary/get_detail only ever
read the last-refreshed row from the database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, ClassVar

from app.config import effective_settings, resolve_timezone
from app.plugins.base import Plugin
from app.storage import db


class PackagesPlugin(Plugin):
    id = "packages"
    name = "Packages"
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {"title": "Packages"}
    # A single grid row is too short for a list of tracked packages — same
    # reasoning as Shopping/Chores/Bookmarks/RSS.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", self.name)

    def _today(self) -> str:
        tz = resolve_timezone(effective_settings()["timezone"])
        return datetime.now(tz).date().isoformat()

    async def _packages(self) -> list[dict[str, Any]]:
        if self.requesting_user_id is None:
            return []
        return await asyncio.to_thread(db.list_packages, self.id, self.requesting_user_id)

    async def get_summary(self) -> dict[str, Any]:
        packages = await self._packages()
        today = self._today()
        active = [p for p in packages if not p["delivered"]]
        arriving_today = [p for p in active if p["eta_date"] == today]
        return {
            "title": self.title,
            "arriving_today_count": len(arriving_today),
            "arriving_today": arriving_today,
            "active_count": len(active),
        }

    async def get_detail(self) -> dict[str, Any]:
        packages = await self._packages()
        summary = await self.get_summary()
        return {**summary, "packages": packages}
