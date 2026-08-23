"""RSS feed plugin: shows one or more feeds from the requesting user's own
feed catalog (`app.storage.db.rss_feeds`), grouped separately by feed."""

from __future__ import annotations

import asyncio
import logging
import re
from calendar import timegm
from typing import Any, ClassVar

import feedparser
import httpx

from app.i18n import t
from app.plugins.base import Plugin, ToolDef
from app.storage import db

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_COMMENTS_LINK_RE = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(?:\d+\s+)?comments?</a>', re.IGNORECASE)


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _clean_summary(text: str) -> str:
    cleaned = _strip_html(text)
    if cleaned.lower() == "comments":
        return ""
    return cleaned


def _extract_comments(entry: Any) -> str | None:
    comments = entry.get("comments")
    if isinstance(comments, str) and comments.strip():
        return comments.strip()
    if isinstance(comments, dict) and comments.get("href"):
        return str(comments["href"]).strip()
    for link in entry.get("links", []):
        if isinstance(link, dict) and link.get("rel") == "replies" and link.get("href"):
            return str(link["href"]).strip()
    for field in ("summary", "description"):
        raw = entry.get(field)
        if isinstance(raw, str):
            m = _COMMENTS_LINK_RE.search(raw)
            if m:
                return m.group(1).strip()
    return None


def _extract_image(entry: Any) -> str | None:
    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail:
        return media_thumbnail[0].get("url")
    media_content = entry.get("media_content")
    if media_content:
        return media_content[0].get("url")
    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("image/"):
            return enclosure.get("href")
    return None


class RSSPlugin(Plugin):
    id = "rss"
    name = "RSS"
    refresh_interval_seconds = 900
    # Each household member reads different headlines, from their own feed
    # catalog — see Plugin.settings_scope.
    settings_scope = "personal"
    default_settings: ClassVar[dict[str, Any]] = {
        "title": "Headlines",
        "feed_ids": [],
    }
    # A single grid row is too short to show a readable headline list without
    # scrolling — start taller so a feed's default item limit fits comfortably.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 2}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", "Headlines")

    @property
    def feed_ids(self) -> list[int]:
        return self.config["settings"].get("feed_ids", [])

    async def _fetch_groups(self, *, include_image: bool) -> list[dict[str, Any]]:
        # requesting_user_id is unset on the registry singleton (before
        # scoped_plugin personalizes it for a request) — no user, no catalog
        # to resolve feed_ids against, so degrade to an empty result rather
        # than querying with a None user_id.
        if self.requesting_user_id is None:
            return []
        feeds = await asyncio.to_thread(db.get_rss_feeds, self.requesting_user_id, self.feed_ids)
        if not feeds:
            return []

        # follow_redirects: a feed that's moved permanently (e.g. a blog's RSS
        # path changing) shouldn't be treated as broken.
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            responses = await asyncio.gather(*(client.get(feed["url"]) for feed in feeds), return_exceptions=True)

        groups: list[dict[str, Any]] = []
        for feed, response in zip(feeds, responses, strict=True):
            # One unreachable or malformed feed shouldn't take down every
            # other feed in the tile — degrade that group to an error rather
            # than letting the exception bubble up and 500 the whole widget.
            try:
                if isinstance(response, BaseException):
                    raise response
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
                if not parsed.version and not parsed.entries:
                    raise parsed.get("bozo_exception") or ValueError("Feed could not be parsed")
            except Exception:
                logger.warning(
                    "Could not load rss feed %s (%s) for widget '%s'", feed["id"], feed["url"], self.id, exc_info=True
                )
                groups.append(
                    {
                        "feed_id": feed["id"],
                        "name": feed.get("name") or feed["url"],
                        "items": [],
                        "error": t("rss.error.feed_unavailable", self.locale),
                    }
                )
                continue

            source = feed.get("name") or parsed.feed.get("title", "")
            items = []
            for entry in parsed.entries[: feed["item_limit"]]:
                item = {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "comments": _extract_comments(entry),
                    "published": entry.get("published"),
                    "published_ts": timegm(entry["published_parsed"]) if entry.get("published_parsed") else 0,
                    "summary": _clean_summary(entry.get("summary", "")),
                    "source": source,
                }
                if include_image:
                    item["image"] = _extract_image(entry)
                items.append(item)
            items.sort(key=lambda e: e["published_ts"], reverse=True)
            for item in items:
                del item["published_ts"]
            groups.append({"feed_id": feed["id"], "name": source, "items": items})
        return groups

    async def get_summary(self) -> dict[str, Any]:
        groups = await self._fetch_groups(include_image=False)
        for group in groups:
            for item in group["items"]:
                item.pop("summary", None)
                item.pop("comments", None)
        return {"title": self.title, "feed_groups": groups}

    async def get_detail(self) -> dict[str, Any]:
        groups = await self._fetch_groups(include_image=True)
        all_feeds = await asyncio.to_thread(db.list_rss_feeds, self.requesting_user_id)
        return {
            "title": self.title,
            "feed_ids": self.feed_ids,
            "all_feeds": all_feeds,
            "feed_groups": groups,
        }

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
