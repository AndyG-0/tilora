from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import alerts
from app.auth import get_current_user
from app.storage import db
from app.storage.cache import cache


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(alerts.router)
    # These tests exercise alert persistence, not auth — stub out who's
    # asking rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_user] = lambda: {"id": "user", "role": "member"}
    return TestClient(app)


def test_create_alert_persists_and_returns_it(client, tmp_db):
    response = client.post("/api/alerts", json={"message": "Hello", "severity": "warning"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Hello"
    assert body["severity"] == "warning"
    assert db.get_alert(body["id"])["message"] == "Hello"


def test_create_alert_defaults_widget_id_to_alert(client, tmp_db):
    response = client.post("/api/alerts", json={"message": "Hi"})

    assert response.json()["widget_id"] == "alert"


def test_create_alert_invalidates_cache(client, tmp_db):
    cache.set("summary:alert", {"stale": True}, ttl_seconds=60)
    cache.set("detail:alert", {"stale": True}, ttl_seconds=60)

    client.post("/api/alerts", json={"message": "Hi"})

    assert cache.get("summary:alert") is None
    assert cache.get("detail:alert") is None


def test_dismiss_alert_marks_dismissed(client, tmp_db):
    alert = db.create_alert("alert", "Bye", "info")

    response = client.post(f"/api/alerts/{alert['id']}/dismiss")

    assert response.status_code == 200
    assert db.get_alert(alert["id"])["dismissed"] is True


def test_dismiss_alert_invalidates_cache(client, tmp_db):
    alert = db.create_alert("alert", "Bye", "info")
    cache.set("summary:alert", {"stale": True}, ttl_seconds=60)
    cache.set("detail:alert", {"stale": True}, ttl_seconds=60)

    client.post(f"/api/alerts/{alert['id']}/dismiss")

    assert cache.get("summary:alert") is None
    assert cache.get("detail:alert") is None


def test_dismiss_alert_returns_404_for_unknown_id(client, tmp_db):
    response = client.post("/api/alerts/9999/dismiss")

    assert response.status_code == 404


def test_alerts_routes_require_a_session():
    app = FastAPI()
    app.include_router(alerts.router)
    client = TestClient(app)

    assert client.post("/api/alerts", json={"message": "Hi"}).status_code == 401
