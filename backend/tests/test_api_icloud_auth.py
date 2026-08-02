from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import icloud_auth
from app.config import settings
from app.integrations import icloud_photos
from app.storage.cache import cache


@pytest.fixture
def client(tmp_db):
    app = FastAPI()
    app.include_router(icloud_auth.router)
    return TestClient(app)


def test_start_auth_returns_400_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "icloud_username", None)
    monkeypatch.setattr(settings, "icloud_password", None)

    response = client.post("/api/icloud/auth/start")

    assert response.status_code == 400


def test_start_auth_connects_and_invalidates_photos_cache(client, monkeypatch):
    monkeypatch.setattr(settings, "icloud_username", "user@example.com")
    monkeypatch.setattr(settings, "icloud_password", "hunter2")

    class FakeService:
        requires_2fa = False

    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: FakeService())
    cache.set("summary:photos", {"stale": True}, 60)
    cache.set("detail:photos", {"stale": True}, 60)

    response = client.post("/api/icloud/auth/start")

    assert response.json() == {"connected": True, "requires_2fa": False}
    assert cache.get("summary:photos") is None
    assert cache.get("detail:photos") is None


def test_start_auth_requires_2fa(client, monkeypatch):
    monkeypatch.setattr(settings, "icloud_username", "user@example.com")
    monkeypatch.setattr(settings, "icloud_password", "hunter2")

    class FakeService:
        requires_2fa = True

    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: FakeService())

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

        def validate_2fa_code(self, code: str) -> bool:
            return code == "123456"

        def trust_session(self) -> None:
            self.is_trusted_session = True

    monkeypatch.setattr(settings, "icloud_username", "user@example.com")
    monkeypatch.setattr(settings, "icloud_password", "hunter2")
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: FakeService())
    client.post("/api/icloud/auth/start")
    cache.set("summary:photos", {"stale": True}, 60)
    cache.set("detail:photos", {"stale": True}, 60)

    response = client.post("/api/icloud/auth/verify", json={"code": "123456"})

    assert response.json() == {"connected": True}
    assert cache.get("summary:photos") is None
    assert cache.get("detail:photos") is None


def test_status_reports_not_connected(client):
    response = client.get("/api/icloud/status")

    assert response.json() == {"connected": False}


def test_status_reports_connected(client):
    cache.set(icloud_photos._SERVICE_CACHE_KEY, object(), 60)

    response = client.get("/api/icloud/status")

    assert response.json() == {"connected": True}
