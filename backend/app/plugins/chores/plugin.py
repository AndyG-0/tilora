"""Chores plugin: a personal to-do/chore list, one per household member.

Unlike Bookmarks/RSS (today's other "personal"-scope plugins, whose lists
live inside the per-user settings blob), each item here is its own DB row
owned by whoever added it — see `Plugin.requesting_user_id`, set by
`app.plugins.scoping.scoped_plugin()` for "personal"-scope plugins. Reads
happen through get_summary/get_detail as usual; writes go through
`app.api.chores`, not settings PATCH, since add/complete/remove are
per-item actions rather than a whole-list replace.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from app.plugins.base import Plugin, ToolDef
from app.storage import db

_NO_USER_ERROR = "No signed-in user for this request; can't access a personal to-do list here."


class ChoresPlugin(Plugin):
    id = "chores"
    name = "To-Do"
    # Each household member keeps their own list — see Plugin.settings_scope.
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {"title": "To-Do"}
    # A single grid row is too short for a checkable list — start taller,
    # like the Bookmarks/RSS widgets.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", self.name)

    async def _chores(self) -> list[dict[str, Any]]:
        # requesting_user_id is unset on the registry singleton (before scoped_plugin
        # personalizes it for a request) and on the AI-insights cron path,
        # which has no signed-in user — an empty list degrades gracefully
        # rather than raising in either case.
        if self.requesting_user_id is None:
            return []
        return await asyncio.to_thread(db.list_chores, self.id, self.requesting_user_id)

    async def get_summary(self) -> dict[str, Any]:
        chores = await self._chores()
        return {
            "title": self.title,
            "chores": chores,
            "open_count": sum(1 for chore in chores if not chore["completed"]),
        }

    async def get_detail(self) -> dict[str, Any]:
        return await self.get_summary()

    def get_ai_tools(self) -> list[ToolDef]:
        async def add_item(text: str) -> dict[str, Any]:
            if self.requesting_user_id is None:
                return {"error": _NO_USER_ERROR}
            return await asyncio.to_thread(db.add_chore, self.id, self.requesting_user_id, text)

        async def complete_item(chore_id: int) -> dict[str, Any]:
            if self.requesting_user_id is None:
                return {"error": _NO_USER_ERROR}
            chore = await asyncio.to_thread(db.complete_chore, chore_id, self.requesting_user_id)
            if chore is None:
                return {"error": f"No to-do item with id {chore_id} found."}
            return chore

        async def remove_item(chore_id: int) -> dict[str, Any]:
            if self.requesting_user_id is None:
                return {"error": _NO_USER_ERROR}
            chore = await asyncio.to_thread(db.remove_chore, chore_id, self.requesting_user_id)
            if chore is None:
                return {"error": f"No to-do item with id {chore_id} found."}
            return {"removed": chore}

        return [
            ToolDef(
                name=f"add_todo_item_{self.id}",
                description=f"Add an item to the '{self.title}' to-do/chore list.",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "The to-do item's text."}},
                    "required": ["text"],
                },
                handler=add_item,
            ),
            ToolDef(
                name=f"complete_todo_item_{self.id}",
                description=f"Mark an item on the '{self.title}' to-do/chore list as done.",
                parameters={
                    "type": "object",
                    "properties": {"chore_id": {"type": "integer", "description": "The to-do item's id."}},
                    "required": ["chore_id"],
                },
                handler=complete_item,
            ),
            ToolDef(
                name=f"remove_todo_item_{self.id}",
                description=f"Remove an item from the '{self.title}' to-do/chore list.",
                parameters={
                    "type": "object",
                    "properties": {"chore_id": {"type": "integer", "description": "The to-do item's id."}},
                    "required": ["chore_id"],
                },
                handler=remove_item,
            ),
        ]
