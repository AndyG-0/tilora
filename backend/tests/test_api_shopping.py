from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import shopping
from app.auth import get_current_user
from app.storage import db
from app.storage.cache import cache


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(shopping.router)
    # These tests exercise item persistence, not auth — stub out who's
    # asking rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1", "name": "Alice", "role": "member"}
    return TestClient(app)


def test_create_item_persists_and_returns_it(client, tmp_db):
    response = client.post("/api/shopping", json={"text": "Milk"})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Milk"
    assert body["added_by"] == "Alice"
    assert db.list_shopping_items("shopping")[0]["text"] == "Milk"


def test_create_item_defaults_widget_id_to_shopping(client, tmp_db):
    response = client.post("/api/shopping", json={"text": "Hi"})

    assert response.json()["widget_id"] == "shopping"


def test_create_item_invalidates_the_shared_cache(client, tmp_db):
    cache.set("summary:shopping:en", {"stale": True}, ttl_seconds=60)
    cache.set("detail:shopping:en", {"stale": True}, ttl_seconds=60)

    client.post("/api/shopping", json={"text": "Hi"})

    assert cache.get("summary:shopping:en") is None
    assert cache.get("detail:shopping:en") is None


def test_check_item_marks_checked_by_the_requesting_user(client, tmp_db):
    item = db.add_shopping_item("shopping", "Eggs", "Bob")

    response = client.post(f"/api/shopping/{item['id']}/check")

    assert response.status_code == 200
    body = response.json()
    assert body["checked"] is True
    assert body["checked_by"] == "Alice"


def test_check_item_toggles_checked_off_item_back_to_open(client, tmp_db):
    item = db.add_shopping_item("shopping", "Eggs", "Bob")
    db.check_shopping_item(item["id"], "Alice")
    cache.set("summary:shopping:en", {"stale": True}, ttl_seconds=60)
    cache.set("detail:shopping:en", {"stale": True}, ttl_seconds=60)

    response = client.post(f"/api/shopping/{item['id']}/check")

    assert response.status_code == 200
    body = response.json()
    assert body["checked"] is False
    assert body["checked_by"] is None
    assert body["checked_at"] is None
    assert cache.get("summary:shopping:en") is None
    assert cache.get("detail:shopping:en") is None


def test_check_item_returns_404_for_unknown_id(client, tmp_db):
    response = client.post("/api/shopping/9999/check")

    assert response.status_code == 404


def test_remove_item_deletes_it(client, tmp_db):
    item = db.add_shopping_item("shopping", "Bye", "Alice")

    response = client.delete(f"/api/shopping/{item['id']}")

    assert response.status_code == 200
    assert db.list_shopping_items("shopping") == []


def test_remove_item_returns_404_for_unknown_id(client, tmp_db):
    response = client.delete("/api/shopping/9999")

    assert response.status_code == 404


def test_shopping_routes_require_a_session():
    app = FastAPI()
    app.include_router(shopping.router)
    client = TestClient(app)

    assert client.post("/api/shopping", json={"text": "Hi"}).status_code == 401
