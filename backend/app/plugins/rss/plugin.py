"""RSS feed plugin: merges one or more feeds into a single reverse-chronological list."""

from __future__ import annotations

import asyncio
import re
from calendar import timegm
from typing import Any, ClassVar

import feedparser
import httpx

from app.plugins.base import Plugin, ToolDef

_SUMMARY_ITEM_COUNT = 5
_DETAIL_ITEM_COUNT = 20
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


class RSSPlugin(Plugin):
    id = "rss"
    name = "RSS"
    refresh_interval_seconds = 900
    # Each household member reads different headlines, not a shared feed —
    # see Plugin.settings_scope.
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {
        "title": "Headlines",
        "feeds": [],
        "item_limit": _SUMMARY_ITEM_COUNT,
    }
    # A single grid row is too short to show a readable headline list without
    # scrolling — start taller so the default item_limit fits comfortably.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", "Headlines")

    @property
    def feeds(self) -> list[dict[str, Any]]:
        return self.config["settings"].get("feeds", [])

    @property
    def item_limit(self) -> int:
        return int(self.config["settings"].get("item_limit", _SUMMARY_ITEM_COUNT))

    async def _fetch_entries(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10) as client:
            responses = await asyncio.gather(*(client.get(feed["url"]) for feed in self.feeds))

        entries: list[dict[str, Any]] = []
        for feed_config, response in zip(self.feeds, responses, strict=True):
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            source = feed_config.get("name") or parsed.feed.get("title", "")
            for entry in parsed.entries:
                published_parsed = entry.get("published_parsed")
                entries.append(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published"),
                        "published_ts": timegm(published_parsed) if published_parsed else 0,
                        "summary": _strip_html(entry.get("summary", "")),
                        "source": source,
                    }
                )
        entries.sort(key=lambda e: e["published_ts"], reverse=True)
        return entries

    async def get_summary(self) -> dict[str, Any]:
        entries = await self._fetch_entries()
        items = [
            {k: v for k, v in e.items() if k not in ("published_ts", "summary")} for e in entries[: self.item_limit]
        ]
        return {"title": self.title, "items": items}

    async def get_detail(self) -> dict[str, Any]:
        entries = await self._fetch_entries()
        items = [{k: v for k, v in e.items() if k != "published_ts"} for e in entries[:_DETAIL_ITEM_COUNT]]
        return {"title": self.title, "feeds": self.feeds, "item_limit": self.item_limit, "items": items}

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_latest_headlines() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name=f"get_latest_headlines_{self.id}",
                description=f"Get the latest headlines from the '{self.title}' RSS widget's configured feeds.",
                parameters={"type": "object", "properties": {}},
                handler=get_latest_headlines,
            )
        ]
