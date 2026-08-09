from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import pihole
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.pihole.plugin import PiholePlugin
from app.storage.cache import cache

AUTH_OK = {"session": {"valid": True, "sid": "sid1", "csrf": "csrf1", "validity": 1800}}


def register_plugin(**settings) -> PiholePlugin:
    merged = {**PiholePlugin.network_default_settings, **PiholePlugin.default_settings, **settings}
    plugin = PiholePlugin({"id": "ph1", "settings": merged})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(pihole.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(pihole.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(pihole.router)
    return TestClient(app)


def test_unknown_widget_returns_404(client):
    response = client.post("/api/pihole/nope/blocking", json={"enabled": True})
    assert response.status_code == 404


def test_set_blocking_requires_login(unauthenticated_client):
    register_plugin(host="pi.local")
    response = unauthenticated_client.post("/api/pihole/ph1/blocking", json={"enabled": True})
    assert response.status_code == 401


def test_set_blocking_rejects_member(member_client):
    register_plugin(host="pi.local")
    response = member_client.post("/api/pihole/ph1/blocking", json={"enabled": True})
    assert response.status_code == 403


@respx.mock
def test_set_blocking_invalidates_cache(client):
    register_plugin(host="pi.local", password="secret")
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.post("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "disabled", "timer": 300})
    )
    cache.set("summary:ph1", {"stale": True}, 60)
    cache.set("detail:ph1", {"stale": True}, 60)

    response = client.post("/api/pihole/ph1/blocking", json={"enabled": False, "timer": 300})

    assert response.json() == {"blocking": "disabled", "timer": 300}
    assert cache.get("summary:ph1") is None
    assert cache.get("detail:ph1") is None


@respx.mock
def test_set_blocking_returns_502_on_pihole_error(client):
    register_plugin(host="pi.local", password="secret")
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(500))

    response = client.post("/api/pihole/ph1/blocking", json={"enabled": True})

    assert response.status_code == 502
