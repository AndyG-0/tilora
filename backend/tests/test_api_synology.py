from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import synology
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.synology.plugin import SynologyPlugin

AUTH_OK = {"success": True, "data": {"sid": "sid1"}}


def register_plugin(**settings) -> SynologyPlugin:
    plugin = SynologyPlugin({"id": "syn1", "settings": {**SynologyPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(synology.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(synology.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(synology.router)
    return TestClient(app)


def test_unknown_widget_returns_404(client):
    response = client.post("/api/synology/nope/test-connection", json={})
    assert response.status_code == 404


def test_test_connection_requires_login(unauthenticated_client):
    register_plugin(host="nas.local")
    response = unauthenticated_client.post("/api/synology/syn1/test-connection", json={})
    assert response.status_code == 401


def test_test_connection_rejects_member(member_client):
    register_plugin(host="nas.local")
    response = member_client.post("/api/synology/syn1/test-connection", json={})
    assert response.status_code == 403


@respx.mock
def test_test_connection_ok(client):
    register_plugin(host="nas.local", username="admin", password="secret")
    respx.get("http://nas.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://nas.local:5000/webapi/query.cgi").mock(
        return_value=httpx.Response(200, json={"data": {"SYNO.Core.System": {"maxVersion": 1}}})
    )
    respx.get("http://nas.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"model": "DS920+"}})
    )

    response = client.post("/api/synology/syn1/test-connection", json={})

    assert response.json() == {"ok": True, "model": "DS920+", "error": None}


@respx.mock
def test_test_connection_uses_candidate_settings_override(client):
    register_plugin(host="nas.local", username="admin", password="secret")
    respx.get("http://other.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://other.local:5000/webapi/query.cgi").mock(
        return_value=httpx.Response(200, json={"data": {"SYNO.Core.System": {"maxVersion": 1}}})
    )
    route = respx.get("http://other.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"model": "DS1520+"}})
    )

    response = client.post("/api/synology/syn1/test-connection", json={"host": "other.local"})

    assert route.called
    assert response.json()["model"] == "DS1520+"


@respx.mock
def test_test_connection_reports_failure_without_raising(client):
    register_plugin(host="nas.local", username="admin", password="wrong")
    respx.get("http://nas.local:5000/webapi/auth.cgi").mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"code": 400}})
    )

    response = client.post("/api/synology/syn1/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]
