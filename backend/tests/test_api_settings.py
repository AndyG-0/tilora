from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings as settings_api
from app.auth import get_current_admin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(settings_api.router)
    # These tests exercise settings persistence, not auth — stub out who's
    # asking rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_admin] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


def test_settings_routes_require_an_admin_session():
    app = FastAPI()
    app.include_router(settings_api.router)
    client = TestClient(app)

    assert client.get("/api/settings").status_code == 401


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


def test_patch_settings_persists_tts_provider_fields(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={
            "openai_tts_enabled": "true",
            "openai_tts_model": "gpt-4o-mini-tts",
            "piper_tts_enabled": "true",
            "piper_server_url": "http://piper.local:5000",
            "piper_voices": "en_US-amy-medium|Amy",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["openai_tts_enabled"] == "true"
    assert body["openai_tts_model"] == "gpt-4o-mini-tts"
    assert body["piper_tts_enabled"] == "true"
    assert body["piper_server_url"] == "http://piper.local:5000"
    assert body["piper_voices"] == "en_US-amy-medium|Amy"


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


def test_patch_settings_persists_agent_name_and_searxng_url(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={
            "ai_agent_name": "Friday",
            "searxng_url": "http://searxng.local:8080",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_agent_name"] == "Friday"
    assert body["searxng_url"] == "http://searxng.local:8080"
