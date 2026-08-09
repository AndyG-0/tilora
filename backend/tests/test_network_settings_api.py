from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import network_settings as network_settings_api
from app.auth import get_current_user
from app.integrations import container_client, hdhomerun_client, pihole_client
from app.plugins.base import registry
from app.plugins.container.plugin import ContainerPlugin
from app.plugins.pihole.plugin import PiholePlugin
from app.storage import db
from app.storage.cache import cache


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(network_settings_api.router)
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


# --- GET /api/network-settings ---------------------------------------------


def test_list_requires_login(unauthenticated_client, tmp_db):
    response = unauthenticated_client.get("/api/network-settings")
    assert response.status_code == 401


def test_list_allows_member_and_masks_secrets(member_client, tmp_db):
    db.save_network_integration(
        "pihole", "pihole", "Pi-hole", {"host": "pi.local", "port": 80, "use_https": False, "password": "secret"}
    )

    response = member_client.get("/api/network-settings")

    assert response.status_code == 200
    row = next(r for r in response.json() if r["id"] == "pihole")
    assert row["settings"]["host"] == "pi.local"
    assert row["settings"]["has_password"] is True
    assert "password" not in row["settings"]


# --- GET /api/network-settings/{type} ---------------------------------------


def test_get_singleton_type(admin_client, tmp_db):
    db.save_network_integration(
        "jellyfin",
        "jellyfin",
        "Jellyfin",
        {
            "host": "jf.local",
            "port": 8096,
            "use_https": False,
            "auth_mode": "api_key",
            "api_key": "k1",
            "username": "",
            "password": "",
        },
    )

    response = admin_client.get("/api/network-settings/jellyfin")

    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["host"] == "jf.local"
    assert body["settings"]["has_api_key"] is True
    assert "api_key" not in body["settings"]


def test_get_container_type_returns_list(admin_client, tmp_db):
    # dashboard.yaml (read by migration 007, which runs as part of tmp_db's
    # db.init_db()) may already define its own container widgets — this only
    # asserts that our own row is present among whatever else migrated in,
    # not that it's the only one.
    db.save_network_integration(
        "container-abc12345", "container", "Docker Test Host", dict(ContainerPlugin.network_default_settings)
    )

    response = admin_client.get("/api/network-settings/container")

    assert response.status_code == 200
    assert "Docker Test Host" in [r["name"] for r in response.json()]


def test_get_unknown_type_returns_404(admin_client, tmp_db):
    response = admin_client.get("/api/network-settings/nope")
    assert response.status_code == 404


# --- PATCH /api/network-settings/{type} -------------------------------------


def test_patch_requires_login(unauthenticated_client, tmp_db):
    response = unauthenticated_client.patch("/api/network-settings/pihole", json={"host": "pi.local"})
    assert response.status_code == 401


def test_patch_rejects_member(member_client, tmp_db):
    response = member_client.patch("/api/network-settings/pihole", json={"host": "pi.local"})
    assert response.status_code == 403


def test_patch_rejects_container_type(admin_client, tmp_db):
    response = admin_client.patch("/api/network-settings/container", json={"host": "x"})
    assert response.status_code == 400


def test_patch_unknown_type_returns_404(admin_client, tmp_db):
    response = admin_client.patch("/api/network-settings/nope", json={})
    assert response.status_code == 404


def test_patch_creates_row_from_defaults_when_none_exists(admin_client, tmp_db):
    response = admin_client.patch("/api/network-settings/pihole", json={"host": "pi.local", "password": "secret"})

    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["host"] == "pi.local"
    assert body["settings"]["has_password"] is True
    stored = db.get_network_integration("pihole")
    assert stored["settings"]["password"] == "secret"


def test_patch_merges_onto_existing_row(admin_client, tmp_db):
    db.save_network_integration(
        "pihole", "pihole", "Pi-hole", {"host": "old.local", "port": 80, "use_https": False, "password": "secret"}
    )

    response = admin_client.patch("/api/network-settings/pihole", json={"host": "new.local"})

    assert response.status_code == 200
    stored = db.get_network_integration("pihole")
    assert stored["settings"]["host"] == "new.local"
    assert stored["settings"]["password"] == "secret"


def test_patch_propagates_live_and_invalidates_cache(admin_client, tmp_db):
    plugin = PiholePlugin({"id": "ph1", "settings": {**PiholePlugin.network_default_settings, "host": "old.local"}})
    registry.register(plugin)
    cache.set("summary:ph1:en", {"stale": True}, 60)
    cache.set("detail:ph1:en", {"stale": True}, 60)

    response = admin_client.patch("/api/network-settings/pihole", json={"host": "new.local"})

    assert response.status_code == 200
    assert plugin.config["settings"]["host"] == "new.local"
    assert cache.get("summary:ph1:en") is None
    assert cache.get("detail:ph1:en") is None


# --- POST /api/network-settings/{type}/test-connection ----------------------


def test_test_connection_requires_login(unauthenticated_client, tmp_db):
    response = unauthenticated_client.post("/api/network-settings/pihole/test-connection", json={})
    assert response.status_code == 401


def test_test_connection_rejects_member(member_client, tmp_db):
    response = member_client.post("/api/network-settings/pihole/test-connection", json={})
    assert response.status_code == 403


def test_test_connection_rejects_container(admin_client, tmp_db):
    response = admin_client.post("/api/network-settings/container/test-connection", json={})
    assert response.status_code == 400


def test_test_connection_rejects_hdhomerun(admin_client, tmp_db):
    response = admin_client.post("/api/network-settings/hdhomerun/test-connection", json={})
    assert response.status_code == 400


def test_test_connection_unknown_type_returns_404(admin_client, tmp_db):
    response = admin_client.post("/api/network-settings/nope/test-connection", json={})
    assert response.status_code == 404


def test_test_connection_dispatches_to_client(admin_client, tmp_db, monkeypatch):
    db.save_network_integration(
        "pihole", "pihole", "Pi-hole", {"host": "pi.local", "port": 80, "use_https": False, "password": "secret"}
    )

    async def fake_test_connection(settings, widget_id):
        assert settings["host"] == "pi.local"
        assert widget_id == "pihole"
        return "v6.3"

    monkeypatch.setitem(network_settings_api._TEST_CONNECTION_DISPATCH, "pihole", fake_test_connection)

    response = admin_client.post("/api/network-settings/pihole/test-connection", json={})

    assert response.json() == {"ok": True, "detail": "v6.3", "error": None}


def test_test_connection_reports_failure_without_raising(admin_client, tmp_db, monkeypatch):
    async def fake_test_connection(settings, widget_id):
        raise pihole_client.PiholeError("boom")

    monkeypatch.setitem(network_settings_api._TEST_CONNECTION_DISPATCH, "pihole", fake_test_connection)

    response = admin_client.post("/api/network-settings/pihole/test-connection", json={})

    assert response.status_code == 200
    assert response.json() == {"ok": False, "detail": None, "error": "boom"}


def test_test_connection_uses_payload_override_onto_saved_settings(admin_client, tmp_db, monkeypatch):
    db.save_network_integration(
        "pihole", "pihole", "Pi-hole", {"host": "pi.local", "port": 80, "use_https": False, "password": "secret"}
    )
    captured: dict[str, object] = {}

    async def fake_test_connection(settings, widget_id):
        captured.update(settings)
        return "ok"

    monkeypatch.setitem(network_settings_api._TEST_CONNECTION_DISPATCH, "pihole", fake_test_connection)

    response = admin_client.post("/api/network-settings/pihole/test-connection", json={"host": "candidate.local"})

    assert response.status_code == 200
    assert captured["host"] == "candidate.local"
    assert captured["password"] == "secret"


# --- POST /api/network-settings/hdhomerun/test-{tuner,dvr}-connection -------


def test_hdhomerun_tuner_test_connection_requires_admin(member_client, tmp_db):
    response = member_client.post("/api/network-settings/hdhomerun/test-tuner-connection", json={})
    assert response.status_code == 403


def test_hdhomerun_tuner_test_connection_ok(admin_client, tmp_db, monkeypatch):
    db.save_network_integration(
        "hdhomerun",
        "hdhomerun",
        "HDHomeRun",
        {"tuner_host": "hdhr.local", "tuner_port": 80, "dvr_host": "", "dvr_port": 59090, "epg_url": ""},
    )

    async def fake(settings):
        assert settings["tuner_host"] == "hdhr.local"
        return "HDHomeRun FLEX"

    monkeypatch.setattr(hdhomerun_client, "test_tuner_connection", fake)

    response = admin_client.post("/api/network-settings/hdhomerun/test-tuner-connection", json={})

    assert response.json() == {"ok": True, "detail": "HDHomeRun FLEX", "error": None}


def test_hdhomerun_dvr_test_connection_reports_failure(admin_client, tmp_db, monkeypatch):
    async def fake(settings):
        raise hdhomerun_client.HDHomeRunError("unreachable")

    monkeypatch.setattr(hdhomerun_client, "test_dvr_connection", fake)

    response = admin_client.post("/api/network-settings/hdhomerun/test-dvr-connection", json={})

    assert response.status_code == 200
    assert response.json() == {"ok": False, "detail": None, "error": "unreachable"}


# --- Container CRUD ----------------------------------------------------------


def test_create_container_integration(admin_client, tmp_db):
    response = admin_client.post(
        "/api/network-settings/container",
        json={"name": "Docker", "engine": "docker", "connection": "tcp", "host": "docker.local", "port": 2375},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Docker"
    assert body["id"].startswith("container-")
    stored = db.get_network_integration(body["id"])
    assert stored["settings"]["host"] == "docker.local"


def test_create_container_integration_requires_name(admin_client, tmp_db):
    response = admin_client.post("/api/network-settings/container", json={"engine": "docker"})
    assert response.status_code == 400


def test_create_container_integration_requires_admin(member_client, tmp_db):
    response = member_client.post("/api/network-settings/container", json={"name": "Docker"})
    assert response.status_code == 403


def test_update_container_integration(admin_client, tmp_db):
    db.save_network_integration(
        "container-abc12345", "container", "Docker", dict(ContainerPlugin.network_default_settings)
    )

    response = admin_client.patch("/api/network-settings/container/container-abc12345", json={"host": "new.local"})

    assert response.status_code == 200
    assert response.json()["settings"]["host"] == "new.local"


def test_update_container_integration_unknown_id_returns_404(admin_client, tmp_db):
    response = admin_client.patch("/api/network-settings/container/nope", json={"host": "x"})
    assert response.status_code == 404


def test_update_container_integration_propagates_live(admin_client, tmp_db):
    db.save_network_integration(
        "container-abc12345", "container", "Docker", dict(ContainerPlugin.network_default_settings)
    )
    plugin = ContainerPlugin({"id": "container", "settings": {"network_integration_id": "container-abc12345"}})
    registry.register(plugin)

    response = admin_client.patch("/api/network-settings/container/container-abc12345", json={"host": "new.local"})

    assert response.status_code == 200
    assert plugin.config["settings"]["host"] == "new.local"


def test_delete_container_integration(admin_client, tmp_db):
    db.save_network_integration(
        "container-abc12345", "container", "Docker", dict(ContainerPlugin.network_default_settings)
    )

    response = admin_client.delete("/api/network-settings/container/container-abc12345")

    assert response.status_code == 200
    assert db.get_network_integration("container-abc12345") is None


def test_delete_container_integration_conflict_when_referenced(admin_client, tmp_db):
    db.save_network_integration(
        "container-abc12345", "container", "Docker", dict(ContainerPlugin.network_default_settings)
    )
    plugin = ContainerPlugin({"id": "container", "settings": {"network_integration_id": "container-abc12345"}})
    registry.register(plugin)

    response = admin_client.delete("/api/network-settings/container/container-abc12345")

    assert response.status_code == 409
    assert db.get_network_integration("container-abc12345") is not None


def test_delete_container_integration_unknown_id_returns_404(admin_client, tmp_db):
    response = admin_client.delete("/api/network-settings/container/nope")
    assert response.status_code == 404


def test_container_test_connection(admin_client, tmp_db, monkeypatch):
    db.save_network_integration(
        "container-abc12345", "container", "Docker", dict(ContainerPlugin.network_default_settings)
    )

    async def fake(settings):
        return "Connected (2 containers found)"

    monkeypatch.setattr(container_client, "test_connection", fake)

    response = admin_client.post("/api/network-settings/container/container-abc12345/test-connection", json={})

    assert response.json() == {"ok": True, "detail": "Connected (2 containers found)", "error": None}


def test_container_test_connection_reports_failure(admin_client, tmp_db, monkeypatch):
    db.save_network_integration(
        "container-abc12345", "container", "Docker", dict(ContainerPlugin.network_default_settings)
    )

    async def fake(settings):
        raise container_client.ContainerError("could not reach the container API")

    monkeypatch.setattr(container_client, "test_connection", fake)

    response = admin_client.post("/api/network-settings/container/container-abc12345/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_container_test_connection_unknown_id_returns_404(admin_client, tmp_db):
    response = admin_client.post("/api/network-settings/container/nope/test-connection", json={})
    assert response.status_code == 404
