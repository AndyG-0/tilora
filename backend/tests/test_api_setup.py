from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import devices as devices_api
from app.api import setup as setup_api
from app.auth import SESSION_COOKIE_NAME
from app.storage import db


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(devices_api.router)
    app.include_router(setup_api.router)
    return TestClient(app)


def test_status_reports_needs_setup_on_a_fresh_install(client, tmp_db):
    response = client.get("/api/setup/status")

    assert response.status_code == 200
    assert response.json() == {"needs_setup": True}


def test_status_flips_to_false_after_the_first_admin_is_created(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/setup/admin", json={"name": "Alice"})

    response = client.get("/api/setup/status")

    assert response.json() == {"needs_setup": False}


def test_create_admin_requires_a_device_cookie(client, tmp_db):
    response = client.post("/api/setup/admin", json={"name": "Alice"})

    assert response.status_code == 401


def test_create_admin_succeeds_and_logs_in_as_admin(client, tmp_db):
    client.post("/api/devices/register")

    response = client.post("/api/setup/admin", json={"name": "Alice", "avatar": "cat.png"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alice"
    assert body["avatar"] == "cat.png"
    assert body["role"] == "admin"
    assert SESSION_COOKIE_NAME in response.cookies
    assert db.get_user(body["id"])["role"] == "admin"


def test_create_admin_returns_409_once_setup_is_already_complete(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/setup/admin", json={"name": "Alice"})

    response = client.post("/api/setup/admin", json={"name": "Bob"})

    assert response.status_code == 409


def test_create_admin_rejects_a_malformed_pin(client, tmp_db):
    client.post("/api/devices/register")

    response = client.post("/api/setup/admin", json={"name": "Alice", "pin": "abc"})

    assert response.status_code == 422


def test_create_admin_with_starter_tiles_preserves_dashboard_yaml(client, tmp_db, tmp_path, monkeypatch):
    import yaml

    from app import config

    config_path = tmp_path / "dashboard.yaml"
    config_path.write_text(yaml.safe_dump({"widgets": [{"id": "weather", "type": "weather", "layout": {}}]}))
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", config_path)

    client.post("/api/devices/register")
    response = client.post("/api/setup/admin", json={"name": "Alice", "include_starter_tiles": True})

    assert response.status_code == 200
    saved = yaml.safe_load(config_path.read_text())
    assert len(saved["widgets"]) == 1


def test_create_admin_without_starter_tiles_clears_dashboard_yaml(client, tmp_db, tmp_path, monkeypatch):
    import yaml

    from app import config

    config_path = tmp_path / "dashboard.yaml"
    config_path.write_text(yaml.safe_dump({"widgets": [{"id": "weather", "type": "weather", "layout": {}}]}))
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", config_path)

    client.post("/api/devices/register")
    response = client.post("/api/setup/admin", json={"name": "Alice", "include_starter_tiles": False})

    assert response.status_code == 200
    saved = yaml.safe_load(config_path.read_text())
    assert saved == {"widgets": []}
