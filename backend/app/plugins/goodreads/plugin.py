"""Goodreads plugin: shows books from a public Goodreads shelf.

Reads Goodreads' still-functioning public shelf RSS export
(`https://www.goodreads.com/review/list_rss/<user_id>?shelf=<shelf>`, no
auth required). Goodreads stuffs book-specific fields (`book_image_url`,
`author_name`, `isbn`, `average_rating`, `user_rating`, `user_date_added`,
`user_read_at`) into each entry as unnamespaced custom tags, which
`feedparser` exposes as plain extra attributes on the entry alongside the
standard `title`/`link`.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import feedparser
import httpx

from app.plugins.base import Plugin

logger = logging.getLogger(__name__)

_SUMMARY_ITEM_COUNT = 5
_DETAIL_ITEM_COUNT = 20


class GoodreadsPlugin(Plugin):
    id = "goodreads"
    name = "Goodreads"
    refresh_interval_seconds = 3600
    default_settings: ClassVar[dict[str, Any]] = {
        "user_id": "",
        "shelf": "currently-reading",
    }
    # A single grid row is too short to show a readable book list without
    # scrolling — start taller, same reasoning as the RSS plugin.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def user_id(self) -> str:
        return self.config["settings"].get("user_id", "")

    @property
    def shelf(self) -> str:
        return self.config["settings"].get("shelf", "currently-reading")

    async def _fetch_books(self) -> list[dict[str, Any]]:
        if not self.user_id:
            return []

        url = f"https://www.goodreads.com/review/list_rss/{self.user_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params={"shelf": self.shelf})
            response.raise_for_status()
        except httpx.HTTPError:
            # A bad user_id or a Goodreads-side hiccup shouldn't 500 the
            # whole widget — that would also lock the settings editor behind
            # the same failing fetch, leaving no way to fix a bad setting
            # from the UI (the editor lives in the detail view it crashes).
            logger.warning("Could not fetch Goodreads shelf for widget '%s'", self.id, exc_info=True)
            return []

        parsed = feedparser.parse(response.content)
        books = []
        for entry in parsed.entries:
            books.append(
                {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "book_image_url": entry.get("book_image_url", ""),
                    "author_name": entry.get("author_name", ""),
                    "isbn": entry.get("isbn", ""),
                    "average_rating": entry.get("average_rating", ""),
                    "user_rating": entry.get("user_rating", ""),
                    "user_date_added": entry.get("user_date_added", ""),
                    "user_read_at": entry.get("user_read_at", ""),
                }
            )
        return books

    async def get_summary(self) -> dict[str, Any]:
        books = await self._fetch_books()
        items = [
            {k: v for k, v in b.items() if k in ("title", "link", "book_image_url", "author_name")}
            for b in books[:_SUMMARY_ITEM_COUNT]
        ]
        return {"shelf": self.shelf, "books": items}

    async def get_detail(self) -> dict[str, Any]:
        books = await self._fetch_books()
        return {
            "shelf": self.shelf,
            "user_id": self.user_id,
            "books": books[:_DETAIL_ITEM_COUNT],
        }
