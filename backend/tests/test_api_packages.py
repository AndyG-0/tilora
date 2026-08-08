from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import packages
from app.auth import get_current_user
from app.config import settings
from app.storage import db
from app.storage.cache import cache


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(packages.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1", "name": "Alice", "role": "member"}
    return TestClient(app)


def test_create_package_requires_a_configured_api_key(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "track17_api_key", None)

    response = client.post("/api/packages", json={"tracking_number": "1Z999AA1"})

    assert response.status_code == 400


@respx.mock
def test_create_package_registers_with_17track_and_persists(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "track17_api_key", "test-key")
    route = respx.post("https://api.17track.net/track/v2.2/register").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"accepted": [{"number": "1Z999AA1"}]}})
    )

    response = client.post("/api/packages", json={"tracking_number": "1Z999AA1", "label": "Gift"})

    assert response.status_code == 200
    assert route.called
    body = response.json()
    assert body["tracking_number"] == "1Z999AA1"
    assert body["label"] == "Gift"
    assert db.list_packages("packages")[0]["tracking_number"] == "1Z999AA1"


@respx.mock
def test_create_package_defaults_widget_id_to_packages(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "track17_api_key", "test-key")
    respx.post("https://api.17track.net/track/v2.2/register").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {}})
    )

    response = client.post("/api/packages", json={"tracking_number": "1Z999AA1"})

    assert response.json()["widget_id"] == "packages"


@respx.mock
def test_create_package_invalidates_the_shared_cache(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "track17_api_key", "test-key")
    respx.post("https://api.17track.net/track/v2.2/register").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {}})
    )
    cache.set("summary:packages:en", {"stale": True}, ttl_seconds=60)
    cache.set("detail:packages:en", {"stale": True}, ttl_seconds=60)

    client.post("/api/packages", json={"tracking_number": "1Z999AA1"})

    assert cache.get("summary:packages:en") is None
    assert cache.get("detail:packages:en") is None


@respx.mock
def test_create_package_returns_502_when_17track_rejects_registration(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "track17_api_key", "test-key")
    respx.post("https://api.17track.net/track/v2.2/register").mock(return_value=httpx.Response(500))

    response = client.post("/api/packages", json={"tracking_number": "1Z999AA1"})

    assert response.status_code == 502
    assert db.list_packages("packages") == []


def test_remove_package_deletes_it(client, tmp_db):
    package = db.add_package("packages", "1Z999AA1")

    response = client.delete(f"/api/packages/{package['id']}")

    assert response.status_code == 200
    assert db.list_packages("packages") == []


def test_remove_package_returns_404_for_unknown_id(client, tmp_db):
    response = client.delete("/api/packages/9999")

    assert response.status_code == 404


def test_package_routes_require_a_session():
    app = FastAPI()
    app.include_router(packages.router)
    client = TestClient(app)

    assert client.post("/api/packages", json={"tracking_number": "1Z999AA1"}).status_code == 401
