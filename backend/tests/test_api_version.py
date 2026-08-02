from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import update_check
from app.api import version


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(version.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_latest():
    update_check._latest["latest_version"] = None
    update_check._latest["release_url"] = None
    yield
    update_check._latest["latest_version"] = None
    update_check._latest["release_url"] = None


def test_get_version_returns_update_status_shape(client, monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "1.0.0")
    update_check._latest["latest_version"] = "1.2.0"
    update_check._latest["release_url"] = "https://github.com/x/releases/tag/v1.2.0"

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {
        "current_version": "1.0.0",
        "latest_version": "1.2.0",
        "update_available": True,
        "release_url": "https://github.com/x/releases/tag/v1.2.0",
    }
