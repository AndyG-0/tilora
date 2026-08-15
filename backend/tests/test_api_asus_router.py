from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import asus_router as asus_router_api
from app.auth import get_current_user
from app.plugins.asus_router.plugin import AsusRouterPlugin
from app.plugins.base import registry


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(asus_router_api.router)
    return app


@pytest.fixture
def admin_client():
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    return TestClient(_app())


@pytest.fixture(autouse=True)
def register_plugin():
    plugin = AsusRouterPlugin(
        {
            "id": "test_router",
            "settings": {"host": "router.local", "ssh_port": 22, "username": "admin", "password": "secret"},
        }
    )
    registry.register(plugin)
    yield
    registry.unregister("test_router")


def test_routes_require_authentication(unauthenticated_client):
    res = unauthenticated_client.post("/api/asus-router/test_router/scan-ports", json={"ip": "192.168.1.10"})
    assert res.status_code == 401


def test_scan_ports_success(member_client):
    with patch(
        "app.integrations.asus_router_client.scan_client_ports",
        new=AsyncMock(
            return_value={
                "ip": "192.168.1.50",
                "open_ports": [
                    {
                        "port": 80,
                        "service": "HTTP",
                        "protocol": "tcp",
                        "is_web": True,
                        "title": "Dashboard",
                    }
                ],
                "web_url": "http://192.168.1.50",
                "scanned_at": "2026-08-14T00:00:00Z",
            }
        ),
    ):
        res = member_client.post("/api/asus-router/test_router/scan-ports", json={"ip": "192.168.1.50"})
        assert res.status_code == 200
        data = res.json()
        assert data["ip"] == "192.168.1.50"
        assert len(data["open_ports"]) == 1
        assert data["web_url"] == "http://192.168.1.50"


def test_scan_ports_invalid_ip(member_client):
    res = member_client.post("/api/asus-router/test_router/scan-ports", json={"ip": "invalid-ip"})
    assert res.status_code == 400


def test_wake_on_lan_success(member_client):
    with patch(
        "app.integrations.asus_router_client.send_wake_on_lan",
        new=AsyncMock(return_value={"ok": True, "mac": "aa:bb:cc:dd:ee:ff", "message": "WOL sent"}),
    ):
        res = member_client.post("/api/asus-router/test_router/wake-on-lan", json={"mac": "aa:bb:cc:dd:ee:ff"})
        assert res.status_code == 200
        assert res.json()["ok"] is True


def test_client_block_admin_only(member_client, admin_client):
    # Member forbidden (write access required for network-scoped plugin)
    res = member_client.post(
        "/api/asus-router/test_router/client-block", json={"mac": "aa:bb:cc:dd:ee:ff", "blocked": True}
    )
    assert res.status_code == 403

    # Admin allowed
    with patch(
        "app.integrations.asus_router_client.set_client_internet_block",
        new=AsyncMock(return_value={"ok": True, "mac": "aa:bb:cc:dd:ee:ff", "blocked": True}),
    ):
        res = admin_client.post(
            "/api/asus-router/test_router/client-block", json={"mac": "aa:bb:cc:dd:ee:ff", "blocked": True}
        )
        assert res.status_code == 200
        assert res.json()["blocked"] is True


def test_client_alias_admin_only(member_client, admin_client):
    res = member_client.post(
        "/api/asus-router/test_router/client-alias", json={"mac": "aa:bb:cc:dd:ee:ff", "alias": "Living Room TV"}
    )
    assert res.status_code == 403

    with patch(
        "app.integrations.asus_router_client.set_client_alias",
        new=AsyncMock(return_value={"ok": True, "mac": "aa:bb:cc:dd:ee:ff", "alias": "Living Room TV"}),
    ):
        res = admin_client.post(
            "/api/asus-router/test_router/client-alias", json={"mac": "aa:bb:cc:dd:ee:ff", "alias": "Living Room TV"}
        )
        assert res.status_code == 200
        assert res.json()["alias"] == "Living Room TV"


def test_ping_endpoint(member_client):
    with patch(
        "app.integrations.asus_router_client.ping_client",
        new=AsyncMock(return_value={"ip": "192.168.1.10", "alive": True, "latency_ms": 1.4}),
    ):
        res = member_client.post("/api/asus-router/test_router/ping", json={"ip": "192.168.1.10"})
        assert res.status_code == 200
        assert res.json()["alive"] is True
        assert res.json()["latency_ms"] == 1.4
