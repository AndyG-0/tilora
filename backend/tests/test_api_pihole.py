from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import pihole
from app.plugins.base import registry
from app.plugins.pihole.plugin import PiholePlugin
from app.storage.cache import cache

AUTH_OK = {"session": {"valid": True, "sid": "sid1", "csrf": "csrf1", "validity": 1800}}


def register_plugin(**settings) -> PiholePlugin:
    plugin = PiholePlugin({"id": "ph1", "settings": {**PiholePlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(pihole.router)
    return TestClient(app)


def test_unknown_widget_returns_404(client):
    response = client.post("/api/pihole/nope/test-connection", json={})
    assert response.status_code == 404


@respx.mock
def test_test_connection_ok(client):
    register_plugin(host="pi.local", password="secret")
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/info/version").mock(
        return_value=httpx.Response(200, json={"version": {"core": {"local": {"version": "v6.0.1"}}}})
    )

    response = client.post("/api/pihole/ph1/test-connection", json={})

    assert response.json() == {"ok": True, "version": "v6.0.1", "error": None}


@respx.mock
def test_test_connection_uses_candidate_settings_override(client):
    register_plugin(host="pi.local", password="secret")
    respx.post("http://other.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    route = respx.get("http://other.local:80/api/info/version").mock(
        return_value=httpx.Response(200, json={"version": {"core": {"local": {"version": "v6.1.0"}}}})
    )

    response = client.post("/api/pihole/ph1/test-connection", json={"host": "other.local"})

    assert route.called
    assert response.json()["version"] == "v6.1.0"


@respx.mock
def test_test_connection_reports_failure_without_raising(client):
    register_plugin(host="pi.local", password="wrong")
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(401))

    response = client.post("/api/pihole/ph1/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]


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
