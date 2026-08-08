from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chores
from app.auth import get_current_user
from app.storage import db
from app.storage.cache import cache


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(chores.router)
    # These tests exercise chore persistence, not auth — stub out who's
    # asking rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1", "role": "member"}
    return TestClient(app)


def test_create_chore_persists_and_returns_it(client, tmp_db):
    response = client.post("/api/chores", json={"text": "Take out trash"})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Take out trash"
    assert body["user_id"] == "user-1"
    assert db.list_chores("chores", "user-1")[0]["text"] == "Take out trash"


def test_create_chore_defaults_widget_id_to_chores(client, tmp_db):
    response = client.post("/api/chores", json={"text": "Hi"})

    assert response.json()["widget_id"] == "chores"


def test_create_chore_invalidates_this_users_cache(client, tmp_db):
    cache.set("summary:chores:user-1:en", {"stale": True}, ttl_seconds=60)
    cache.set("detail:chores:user-1:en", {"stale": True}, ttl_seconds=60)

    client.post("/api/chores", json={"text": "Hi"})

    assert cache.get("summary:chores:user-1:en") is None
    assert cache.get("detail:chores:user-1:en") is None


def test_complete_chore_marks_done(client, tmp_db):
    chore = db.add_chore("chores", "user-1", "Finish me")

    response = client.post(f"/api/chores/{chore['id']}/complete")

    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_complete_chore_returns_404_for_unknown_id(client, tmp_db):
    response = client.post("/api/chores/9999/complete")

    assert response.status_code == 404


def test_complete_chore_returns_404_for_another_users_item(client, tmp_db):
    chore = db.add_chore("chores", "someone-else", "Not yours")

    response = client.post(f"/api/chores/{chore['id']}/complete")

    assert response.status_code == 404


def test_remove_chore_deletes_it(client, tmp_db):
    chore = db.add_chore("chores", "user-1", "Bye")

    response = client.delete(f"/api/chores/{chore['id']}")

    assert response.status_code == 200
    assert db.list_chores("chores", "user-1") == []


def test_remove_chore_returns_404_for_another_users_item(client, tmp_db):
    chore = db.add_chore("chores", "someone-else", "Not yours")

    response = client.delete(f"/api/chores/{chore['id']}")

    assert response.status_code == 404


def test_chores_routes_require_a_session():
    app = FastAPI()
    app.include_router(chores.router)
    client = TestClient(app)

    assert client.post("/api/chores", json={"text": "Hi"}).status_code == 401
