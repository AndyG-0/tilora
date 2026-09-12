from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.rss.plugin import RSSPlugin
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/rss", tags=["rss"], dependencies=[Depends(get_current_user)])

_MAX_REDIRECTS = 5


def _is_blocked_address(host: str) -> bool:
    # A feed URL is otherwise free to point anywhere, including a LAN IP
    # (Tilora already trusts admins to point other integrations - Pi-hole,
    # Jellyfin, HDHomeRun, etc - straight at LAN devices) - but loopback,
    # link-local (which covers the 169.254.169.254-style cloud metadata
    # endpoint), and multicast/reserved addresses are never a legitimate
    # feed source, so resolving to one is always rejected regardless of
    # what the URL's own hostname claims to be.
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        # Can't resolve it at all - not a block in itself (the fetch below
        # will just fail with its own "could not load a feed" error), only
        # a resolvable loopback/link-local/etc target is a confirmed block.
        return False
    return any(
        ipaddress.ip_address(addr).is_loopback
        or ipaddress.ip_address(addr).is_link_local
        or ipaddress.ip_address(addr).is_multicast
        or ipaddress.ip_address(addr).is_reserved
        for addr in addrs
    )


async def _assert_safe_feed_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Feed url must be a valid http(s) URL")
    if await asyncio.to_thread(_is_blocked_address, parsed.hostname):
        raise HTTPException(status_code=400, detail="That URL is not allowed as a feed source")


async def _validate_feed_url(url: str) -> None:
    # Catch a bad feed at add time rather than letting it 500 the widget on
    # every later refresh — the settings editor is the only place a user can
    # fix or remove a broken url, so it needs to reject one up front.
    await _assert_safe_feed_url(url)
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            current_url = url
            for _ in range(_MAX_REDIRECTS + 1):
                response = await client.get(current_url)
                if response.is_redirect:
                    current_url = str(response.next_request.url) if response.next_request else current_url
                    await _assert_safe_feed_url(current_url)
                    continue
                break
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
