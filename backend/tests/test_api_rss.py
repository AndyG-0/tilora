from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import rss
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.rss.plugin import RSSPlugin
from app.storage import db
from app.storage.cache import cache

VALID_FEED = b"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>A</title>
<item><title>Item</title><link>https://example.com/item</link></item>
</channel>
</rss>
"""


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rss.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1", "name": "Alice", "role": "member"}
    return TestClient(app)


def test_list_feeds_returns_the_requesting_users_catalog(client, tmp_db):
    db.add_rss_feed("user-1", "https://a.example/feed.xml", None)
    db.add_rss_feed("user-2", "https://b.example/feed.xml", None)

    response = client.get("/api/rss/feeds")

    assert response.status_code == 200
    urls = [feed["url"] for feed in response.json()]
    assert urls == ["https://a.example/feed.xml"]


@respx.mock
def test_add_feed_persists_and_returns_it(client, tmp_db):
    respx.get("https://a.example/feed.xml").mock(return_value=httpx.Response(200, content=VALID_FEED))

    response = client.post("/api/rss/feeds", json={"url": "https://a.example/feed.xml", "name": "A"})

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "https://a.example/feed.xml"
    assert body["name"] == "A"
    assert body["item_limit"] == 10
    assert db.list_rss_feeds("user-1")[0]["url"] == "https://a.example/feed.xml"


def test_add_feed_requires_a_url(client, tmp_db):
    response = client.post("/api/rss/feeds", json={"url": ""})

    assert response.status_code == 400


@respx.mock
def test_add_feed_rejects_an_unreachable_url(client, tmp_db):
    respx.get("https://a.example/feed.xml").mock(return_value=httpx.Response(404))

    response = client.post("/api/rss/feeds", json={"url": "https://a.example/feed.xml"})

    assert response.status_code == 400
    assert db.list_rss_feeds("user-1") == []


@respx.mock
def test_add_feed_rejects_a_url_that_is_not_a_feed(client, tmp_db):
    respx.get("https://a.example/feed.xml").mock(return_value=httpx.Response(200, content=b"<html></html>"))

    response = client.post("/api/rss/feeds", json={"url": "https://a.example/feed.xml"})

    assert response.status_code == 400
    assert db.list_rss_feeds("user-1") == []


@respx.mock
def test_add_feed_invalidates_every_rss_widgets_cache_for_this_user(client, tmp_db):
    respx.get("https://a.example/feed.xml").mock(return_value=httpx.Response(200, content=VALID_FEED))
    registry.register(RSSPlugin({"id": "rss", "settings": {}}))
    registry.register(RSSPlugin({"id": "rss-abc12345", "settings": {}}))
    cache.set("summary:rss:user-1:en", {"stale": True}, ttl_seconds=60)
    cache.set("detail:rss-abc12345:user-1:en", {"stale": True}, ttl_seconds=60)
    # A different user's cached copy is untouched by this user's edit.
    cache.set("summary:rss:user-2:en", {"stale": True}, ttl_seconds=60)

    client.post("/api/rss/feeds", json={"url": "https://a.example/feed.xml"})

    assert cache.get("summary:rss:user-1:en") is None
    assert cache.get("detail:rss-abc12345:user-1:en") is None
    assert cache.get("summary:rss:user-2:en") == {"stale": True}


def test_update_feed_changes_name_and_item_limit(client, tmp_db):
    feed = db.add_rss_feed("user-1", "https://a.example/feed.xml", "Old")

    response = client.patch(f"/api/rss/feeds/{feed['id']}", json={"name": "New", "item_limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New"
    assert body["item_limit"] == 3


def test_update_feed_returns_404_for_unknown_id(client, tmp_db):
    response = client.patch("/api/rss/feeds/9999", json={"name": "New", "item_limit": 3})

    assert response.status_code == 404


def test_update_feed_cannot_touch_another_users_feed(client, tmp_db):
    feed = db.add_rss_feed("user-2", "https://a.example/feed.xml", None)

    response = client.patch(f"/api/rss/feeds/{feed['id']}", json={"name": "New", "item_limit": 3})

    assert response.status_code == 404


def test_remove_feed_deletes_it(client, tmp_db):
    feed = db.add_rss_feed("user-1", "https://a.example/feed.xml", None)

    response = client.delete(f"/api/rss/feeds/{feed['id']}")

    assert response.status_code == 200
    assert db.list_rss_feeds("user-1") == []


def test_remove_feed_cannot_touch_another_users_feed(client, tmp_db):
    feed = db.add_rss_feed("user-2", "https://a.example/feed.xml", None)

    client.delete(f"/api/rss/feeds/{feed['id']}")

    assert db.list_rss_feeds("user-2") == [feed]


def test_rss_routes_require_a_session():
    app = FastAPI()
    app.include_router(rss.router)
    client = TestClient(app)

    assert client.get("/api/rss/feeds").status_code == 401
