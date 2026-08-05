"""Bookmarks plugin: a personal list of named links."""

from __future__ import annotations

from typing import Any, ClassVar

from app.plugins.base import Plugin, ToolDef


class BookmarksPlugin(Plugin):
    id = "bookmarks"
    name = "Bookmarks"
    # Each household member keeps their own links, not a shared list — see
    # Plugin.settings_scope.
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {"title": "Bookmarks", "bookmarks": []}
    # A single grid row is too short to show more than a couple of links
    # without scrolling — start taller like the RSS widget.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", "Bookmarks")

    @property
    def bookmarks(self) -> list[dict[str, Any]]:
        return self.config["settings"].get("bookmarks", [])

    async def get_summary(self) -> dict[str, Any]:
        return {"title": self.title, "bookmarks": self.bookmarks}

    async def get_detail(self) -> dict[str, Any]:
        return {"title": self.title, "bookmarks": self.bookmarks}

    def get_ai_tools(self) -> list[ToolDef]:
        async def list_bookmarks() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name=f"list_bookmarks_{self.id}",
                description=f"List the saved links in the '{self.title}' bookmarks widget.",
                parameters={"type": "object", "properties": {}},
                handler=list_bookmarks,
            )
        ]
