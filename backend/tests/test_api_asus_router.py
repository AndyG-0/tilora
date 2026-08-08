from __future__ import annotations

from dataclasses import dataclass

import asyncssh
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import asus_router
from app.auth import get_current_user
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
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(asus_router.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(asus_router.router)
    return TestClient(app)


@dataclass
class _FakeCompletedProcess:
    stdout: str


def _productid_output(productid: str) -> str:
    sections = [
        ("WAN_STATE", "4"),
        ("WAN_IP", ""),
        ("WAN_IFNAME", "eth0"),
        ("PRODUCTID", productid),
        ("NETDEV", ""),
        ("LEASES", ""),
        ("ARP", ""),
    ]
    lines = [line for name, value in sections for line in (f"@@{name}@@", value)]
    return "\n".join(lines)


def _fake_connect_by_host(productid_by_host: dict[str, str]):
    async def fake_connect(host, *, port, username, password, known_hosts):
        class _Conn:
            async def run(self, command, check=False):
                return _FakeCompletedProcess(stdout=_productid_output(productid_by_host[host]))

            def close(self):
                pass

            async def wait_closed(self):
                pass

        return _Conn()

    return fake_connect


def test_unknown_widget_returns_404(client):
    response = client.post("/api/asus-router/nope/test-connection", json={})
    assert response.status_code == 404


def test_test_connection_requires_login(unauthenticated_client):
    register_plugin(host="router.local")
    response = unauthenticated_client.post("/api/asus-router/ar1/test-connection", json={})
    assert response.status_code == 401


def test_test_connection_rejects_member(member_client):
    register_plugin(host="router.local")
    response = member_client.post("/api/asus-router/ar1/test-connection", json={})
    assert response.status_code == 403


def test_test_connection_ok(client, monkeypatch):
    monkeypatch.setattr(asyncssh, "connect", _fake_connect_by_host({"router.local": "RT-AX88U"}))
    register_plugin(host="router.local", username="admin", password="secret")

    response = client.post("/api/asus-router/ar1/test-connection", json={})

    assert response.json() == {"ok": True, "product_id": "RT-AX88U", "error": None}


def test_test_connection_uses_candidate_settings_override(client, monkeypatch):
    monkeypatch.setattr(
        asyncssh, "connect", _fake_connect_by_host({"router.local": "RT-AX88U", "other.local": "RT-AX86U"})
    )
    register_plugin(host="router.local", username="admin", password="secret")

    response = client.post("/api/asus-router/ar1/test-connection", json={"host": "other.local"})

    assert response.json()["product_id"] == "RT-AX86U"


def test_test_connection_reports_failure_without_raising(client, monkeypatch):
    async def fake_connect(host, *, port, username, password, known_hosts):
        raise asyncssh.PermissionDenied("auth failed")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    register_plugin(host="router.local", username="admin", password="wrong")

    response = client.post("/api/asus-router/ar1/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]
