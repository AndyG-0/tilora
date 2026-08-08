"""Shopping plugin: a shared household shopping/grocery list.

Unlike Chores (a personal list per household member), this is a plain
`"network"`-scope plugin — one shared list for the whole household, with
per-item attribution (`added_by`/`checked_by`) rather than per-user
ownership. Reads happen through get_summary/get_detail as usual; writes go
through `app.api.shopping`, not settings PATCH, since add/check/remove are
per-item actions rather than a whole-list replace.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from app.plugins.base import Plugin
from app.storage import db


class ShoppingPlugin(Plugin):
    id = "shopping"
    name = "Shopping List"
    default_settings: ClassVar[dict[str, Any]] = {"title": "Shopping List"}
    # A single grid row is too short for a checkable list — start taller,
    # like the Bookmarks/RSS/Chores widgets.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", self.name)

    async def _items(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(db.list_shopping_items, self.id)

    async def get_summary(self) -> dict[str, Any]:
        items = await self._items()
        return {
            "title": self.title,
            "items": items,
            "open_count": sum(1 for item in items if not item["checked"]),
        }

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()
