from __future__ import annotations

import asyncio
from typing import Any

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.rss.plugin import RSSPlugin
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/rss", tags=["rss"], dependencies=[Depends(get_current_user)])


async def _validate_feed_url(url: str) -> None:
    # Catch a bad feed at add time rather than letting it 500 the widget on
    # every later refresh — the settings editor is the only place a user can
    # fix or remove a broken url, so it needs to reject one up front.
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail="Could not load a feed from that URL") from exc

    parsed = feedparser.parse(response.content)
    if not parsed.version and not parsed.entries:
        raise HTTPException(status_code=400, detail="That URL does not look like a valid RSS/Atom feed")


def _invalidate(user_id: str) -> None:
    # A feed catalog is shared across however many RSS tiles this user has,
    # not tied to one widget_id, so — unlike app.api.chores/shopping, which
    # know the single widget_id a change affects — sweep every live RSS
    # widget instance's cache for this user rather than just one.
    for plugin in registry.all():
        if isinstance(plugin, RSSPlugin):
            cache.delete_prefix(f"summary:{plugin.id}:{user_id}:")
            cache.delete_prefix(f"detail:{plugin.id}:{user_id}:")


@router.get("/feeds")
async def list_feeds(user: dict[str, Any] = Depends(get_current_user)):
    return await asyncio.to_thread(db.list_rss_feeds, user["id"])


@router.post("/feeds")
async def add_feed(payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    url = payload.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="A feed url is required")
    name = (payload.get("name") or "").strip() or None
    item_limit = int(payload.get("item_limit", 10))
    await _validate_feed_url(url)
    feed = await asyncio.to_thread(db.add_rss_feed, user["id"], url, name, item_limit)
    _invalidate(user["id"])
    return feed


@router.patch("/feeds/{feed_id}")
async def update_feed(feed_id: int, payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    name = (payload.get("name") or "").strip() or None
    item_limit = int(payload.get("item_limit", 10))
    feed = await asyncio.to_thread(db.update_rss_feed, user["id"], feed_id, name, item_limit)
    if feed is None:
        raise HTTPException(status_code=404, detail=f"Unknown feed '{feed_id}'")
    _invalidate(user["id"])
    return feed


@router.delete("/feeds/{feed_id}")
async def remove_feed(feed_id: int, user: dict[str, Any] = Depends(get_current_user)):
    await asyncio.to_thread(db.delete_rss_feed, user["id"], feed_id)
    _invalidate(user["id"])
    return {"status": "ok"}
