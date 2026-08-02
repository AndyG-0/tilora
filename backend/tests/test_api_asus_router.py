from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import asus_router
from app.plugins.asus_router.plugin import AsusRouterPlugin
from app.plugins.base import registry


def register_plugin(**settings) -> AsusRouterPlugin:
    plugin = AsusRouterPlugin({"id": "ar1", "settings": {**AsusRouterPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(asus_router.router)
    return TestClient(app)


def test_unknown_widget_returns_404(client):
    response = client.post("/api/asus-router/nope/test-connection", json={})
    assert response.status_code == 404


@respx.mock
def test_test_connection_ok(client):
    register_plugin(host="router.local", username="admin", password="secret")
    respx.post("https://router.local/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok1"}))
    respx.post("https://router.local/appGet.cgi").mock(return_value=httpx.Response(200, json={"productid": "RT-AX88U"}))

    response = client.post("/api/asus-router/ar1/test-connection", json={})

    assert response.json() == {"ok": True, "product_id": "RT-AX88U", "error": None}


@respx.mock
def test_test_connection_uses_candidate_settings_override(client):
    register_plugin(host="router.local", username="admin", password="secret")
    respx.post("https://other.local/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok2"}))
    route = respx.post("https://other.local/appGet.cgi").mock(
        return_value=httpx.Response(200, json={"productid": "RT-AX86U"})
    )

    response = client.post("/api/asus-router/ar1/test-connection", json={"host": "other.local"})

    assert route.called
    assert response.json()["product_id"] == "RT-AX86U"


@respx.mock
def test_test_connection_reports_failure_without_raising(client):
    register_plugin(host="router.local", username="admin", password="wrong")
    respx.post("https://router.local/login.cgi").mock(return_value=httpx.Response(200, json={}))

    response = client.post("/api/asus-router/ar1/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]
