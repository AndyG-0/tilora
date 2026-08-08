from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import qbittorrent
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.qbittorrent.plugin import QBittorrentPlugin


def register_plugin(**settings) -> QBittorrentPlugin:
    plugin = QBittorrentPlugin({"id": "qb1", "settings": {**QBittorrentPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(qbittorrent.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(qbittorrent.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(qbittorrent.router)
    return TestClient(app)


def test_unknown_widget_returns_404(client):
    response = client.post("/api/qbittorrent/nope/test-connection", json={})
    assert response.status_code == 404


def test_test_connection_requires_login(unauthenticated_client):
    register_plugin(host="qbit.local")
    response = unauthenticated_client.post("/api/qbittorrent/qb1/test-connection", json={})
    assert response.status_code == 401


def test_test_connection_rejects_member(member_client):
    register_plugin(host="qbit.local")
    response = member_client.post("/api/qbittorrent/qb1/test-connection", json={})
    assert response.status_code == 403


@respx.mock
def test_test_connection_ok(client):
    register_plugin(host="qbit.local", password="secret")
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(
        return_value=httpx.Response(200, text="Ok.", headers={"Set-Cookie": "SID=abc; Path=/"})
    )
    respx.get("http://qbit.local:8080/api/v2/app/version").mock(return_value=httpx.Response(200, text="v4.6.0"))

    response = client.post("/api/qbittorrent/qb1/test-connection", json={})

    assert response.json() == {"ok": True, "version": "4.6.0", "error": None}


@respx.mock
def test_test_connection_reports_failure_without_raising(client):
    register_plugin(host="qbit.local", password="wrong")
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=httpx.Response(200, text="Fails."))

    response = client.post("/api/qbittorrent/qb1/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]
