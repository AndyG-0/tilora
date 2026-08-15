from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import update_check
from app.api import system as system_api
from app.auth import get_current_admin
from app.storage import db


@pytest.fixture
def client(tmp_db):
    app = FastAPI()
    app.include_router(system_api.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_update_state():
    update_check._update_state["running"] = False
    update_check._update_state["error"] = None
    yield
    update_check._update_state["running"] = False
    update_check._update_state["error"] = None


def _seed_admin():
    db.create_user("admin1", "Admin", None, None, None, None, "2026-01-01T00:00:00Z", role="admin")


def test_trigger_update_requires_authentication(client):
    response = client.post("/api/system/update")

    assert response.status_code == 401


def test_trigger_update_rejects_non_native_install(client, monkeypatch):
    _seed_admin()
    client.app.dependency_overrides[get_current_admin] = lambda: db.get_user("admin1")
    monkeypatch.setattr(system_api, "INSTALL_METHOD", "")

    response = client.post("/api/system/update")

    assert response.status_code == 400
    assert "native" in response.json()["detail"].lower()


def test_trigger_update_returns_409_when_already_running(client, monkeypatch):
    _seed_admin()
    client.app.dependency_overrides[get_current_admin] = lambda: db.get_user("admin1")
    monkeypatch.setattr(system_api, "INSTALL_METHOD", "native")
    update_check._update_state["running"] = True

    response = client.post("/api/system/update")

    assert response.status_code == 409
    assert "progress" in response.json()["detail"].lower()


def test_trigger_update_queues_background_task_on_native_install(client, monkeypatch):
    _seed_admin()
    client.app.dependency_overrides[get_current_admin] = lambda: db.get_user("admin1")
    monkeypatch.setattr(system_api, "INSTALL_METHOD", "native")

    # Patch run_update on the system_api module where the name is bound.
    ran = []

    async def fake_run_update():
        ran.append(True)

    monkeypatch.setattr(system_api, "run_update", fake_run_update)

    response = client.post("/api/system/update")

    assert response.status_code == 200
    assert response.json() == {"status": "update_started"}
    # Background tasks run synchronously in TestClient.
    assert len(ran) == 1
