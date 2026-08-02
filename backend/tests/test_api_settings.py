from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings as settings_api


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(settings_api.router)
    return TestClient(app)


def test_get_settings_never_returns_raw_secret_values(client, tmp_db):
    from app.storage import db

    db.save_app_settings({"anthropic_api_key": "sk-secret"})

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert "anthropic_api_key" not in body
    assert body["has_anthropic_api_key"] is True
    assert body["has_openai_api_key"] is False
    assert body["has_gemini_api_key"] is False


def test_patch_settings_persists_timezone_and_model(client, tmp_db):
    response = client.patch(
        "/api/settings", json={"timezone": "America/Chicago", "ai_model": "gemini/gemini-2.5-flash"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "America/Chicago"
    assert body["ai_model"] == "gemini/gemini-2.5-flash"


def test_patch_settings_sets_and_reports_key_presence(client, tmp_db):
    response = client.patch("/api/settings", json={"gemini_api_key": "gm-secret"})

    assert response.status_code == 200
    assert response.json()["has_gemini_api_key"] is True


def test_patch_settings_empty_string_clears_key(client, tmp_db):
    client.patch("/api/settings", json={"gemini_api_key": "gm-secret"})

    response = client.patch("/api/settings", json={"gemini_api_key": ""})

    assert response.status_code == 200
    assert response.json()["has_gemini_api_key"] is False


def test_patch_settings_caldav_url_and_username_round_trip_but_password_is_hidden(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={
            "caldav_url": "https://caldav.example.com",
            "caldav_username": "alice",
            "caldav_password": "secret",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["caldav_url"] == "https://caldav.example.com"
    assert body["caldav_username"] == "alice"
    assert "caldav_password" not in body
    assert body["has_caldav_password"] is True


def test_patch_settings_icloud_username_round_trips_but_password_is_hidden(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={"icloud_username": "user@example.com", "icloud_password": "hunter2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["icloud_username"] == "user@example.com"
    assert "icloud_password" not in body
    assert body["has_icloud_password"] is True


def test_patch_settings_invalidates_clock_and_date_widget_cache(client, tmp_db):
    from app.storage.cache import cache

    cache.set("summary:clock", {"timezone": "UTC"}, 3600)
    cache.set("detail:clock", {"timezone": "UTC"}, 3600)
    cache.set("summary:date", {"timezone": "UTC"}, 3600)
    cache.set("detail:date", {"timezone": "UTC"}, 3600)

    client.patch("/api/settings", json={"timezone": "America/New_York"})

    assert cache.get("summary:clock") is None
    assert cache.get("detail:clock") is None
    assert cache.get("summary:date") is None
    assert cache.get("detail:date") is None
