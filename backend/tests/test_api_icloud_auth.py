from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import icloud_auth
from app.auth import get_current_user
from app.integrations import icloud_photos
from app.plugins.base import registry
from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db
from app.storage.cache import cache

USER_ID = "alice"


def register_plugin(**settings) -> PhotosPlugin:
    """Registers a photos widget the same way the live registry does — see
    `register_plugin` in test_api_photos.py."""
    plugin = PhotosPlugin({"id": "photos", "settings": {**PhotosPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client(tmp_db):
    app = FastAPI()
    app.include_router(icloud_auth.router)
    # These tests exercise the connect flow, not auth — stub out who's
    # asking rather than juggling real device/session cookies here. Any
    # logged-in household member may connect their own Apple ID (personal
    # credential, not admin-gated) — see icloud_auth's module docstring.
    app.dependency_overrides[get_current_user] = lambda: {"id": USER_ID, "role": "member"}
    return TestClient(app)


def _save_credentials(username="user@example.com", password="hunter2"):
    db.save_user_credentials(USER_ID, "icloud", {"username": username, "password": password})


def test_start_auth_returns_400_when_not_configured(client):
    response = client.post("/api/icloud/auth/start")

    assert response.status_code == 400


def test_start_auth_connects_and_invalidates_photos_cache(client, monkeypatch):
    register_plugin()
    _save_credentials()

    class FakeService:
        requires_2fa = False

    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: FakeService())
    cache.set(f"summary:photos:{USER_ID}:en", {"stale": True}, 60)
    cache.set(f"detail:photos:{USER_ID}:en", {"stale": True}, 60)

    response = client.post("/api/icloud/auth/start")

    assert response.json() == {"connected": True, "requires_2fa": False}
    assert cache.get(f"summary:photos:{USER_ID}:en") is None
    assert cache.get(f"detail:photos:{USER_ID}:en") is None


def test_start_auth_requires_2fa(client, monkeypatch):
    _save_credentials()

    class FakeService:
        requires_2fa = True

        def trigger_2fa_push_notification(self) -> bool:
            return True

    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: FakeService())

    response = client.post("/api/icloud/auth/start")

    assert response.json() == {"connected": False, "requires_2fa": True}


def test_verify_auth_requires_code(client):
    response = client.post("/api/icloud/auth/verify", json={})

    assert response.status_code == 400


def test_verify_auth_rejects_when_no_pending_session(client):
    response = client.post("/api/icloud/auth/verify", json={"code": "123456"})

    assert response.json() == {"connected": False}


def test_verify_auth_succeeds_and_invalidates_photos_cache(client, monkeypatch):
    class FakeService:
        requires_2fa = True
        is_trusted_session = False

        def trigger_2fa_push_notification(self) -> bool:
            return True

        def validate_2fa_code(self, code: str) -> bool:
            return code == "123456"

        def trust_session(self) -> None:
            self.is_trusted_session = True

    register_plugin()
    _save_credentials()
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: FakeService())
    client.post("/api/icloud/auth/start")
    cache.set(f"summary:photos:{USER_ID}:en", {"stale": True}, 60)
    cache.set(f"detail:photos:{USER_ID}:en", {"stale": True}, 60)

    response = client.post("/api/icloud/auth/verify", json={"code": "123456"})

    assert response.json() == {"connected": True}
    assert cache.get(f"summary:photos:{USER_ID}:en") is None
    assert cache.get(f"detail:photos:{USER_ID}:en") is None


def test_status_reports_not_connected(client):
    response = client.get("/api/icloud/status")

    assert response.json() == {"connected": False}


def test_status_reports_connected(client):
    cache.set(icloud_photos._service_cache_key(USER_ID), object(), 60)

    response = client.get("/api/icloud/status")

    assert response.json() == {"connected": True}


def test_set_credentials_persists_and_invalidates_stale_session(client, monkeypatch):
    register_plugin()
    invalidated = []
    monkeypatch.setattr(
        icloud_photos, "invalidate_service_cache", lambda user_id, clear_disk=False: invalidated.append(user_id)
    )
    cache.set(f"summary:photos:{USER_ID}:en", {"stale": True}, 60)
    cache.set(f"detail:photos:{USER_ID}:en", {"stale": True}, 60)

    response = client.put("/api/icloud/credentials", json={"username": "user@example.com", "password": "hunter2"})

    assert response.status_code == 200
    assert db.get_user_credentials(USER_ID, "icloud") == {"username": "user@example.com", "password": "hunter2"}
    assert invalidated == [USER_ID]
    assert cache.get(f"summary:photos:{USER_ID}:en") is None
    assert cache.get(f"detail:photos:{USER_ID}:en") is None


def test_set_credentials_requires_both_fields(client):
    response = client.put("/api/icloud/credentials", json={"username": "user@example.com"})

    assert response.status_code == 400
    assert db.get_user_credentials(USER_ID, "icloud") is None


def test_set_credentials_keeps_existing_password_when_omitted(client):
    _save_credentials(username="user@example.com", password="hunter2")

    response = client.put("/api/icloud/credentials", json={"username": "new@example.com"})

    assert response.status_code == 200
    assert response.json() == {"username": "new@example.com", "has_password": True}
    assert db.get_user_credentials(USER_ID, "icloud") == {"username": "new@example.com", "password": "hunter2"}


def test_set_credentials_keeps_existing_username_when_omitted(client):
    _save_credentials(username="user@example.com", password="hunter2")

    response = client.put("/api/icloud/credentials", json={"password": "new-password"})

    assert response.status_code == 200
    assert response.json() == {"username": "user@example.com", "has_password": True}
    assert db.get_user_credentials(USER_ID, "icloud") == {"username": "user@example.com", "password": "new-password"}


def test_get_credentials_when_not_configured(client):
    response = client.get("/api/icloud/credentials")

    assert response.json() == {"username": "", "has_password": False}


def test_get_credentials_returns_username_without_password(client):
    _save_credentials(username="user@example.com", password="hunter2")

    response = client.get("/api/icloud/credentials")

    assert response.json() == {"username": "user@example.com", "has_password": True}


def test_clear_credentials_removes_them_and_invalidates_session(client, monkeypatch):
    _save_credentials()
    invalidated = []
    monkeypatch.setattr(
        icloud_photos, "invalidate_service_cache", lambda user_id, clear_disk=False: invalidated.append(user_id)
    )

    response = client.delete("/api/icloud/credentials")

    assert response.status_code == 200
    assert db.get_user_credentials(USER_ID, "icloud") is None
    assert invalidated == [USER_ID]


def test_icloud_routes_require_a_logged_in_user(tmp_db):
    app = FastAPI()
    app.include_router(icloud_auth.router)
    client = TestClient(app)

    assert client.get("/api/icloud/status").status_code == 401
