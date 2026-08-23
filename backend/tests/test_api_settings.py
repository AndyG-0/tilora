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


def test_patch_settings_persists_stt_provider_fields(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={
            "openai_stt_enabled": "true",
            "openai_stt_model": "whisper-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["openai_stt_enabled"] == "true"
    assert body["openai_stt_model"] == "whisper-1"


def test_patch_settings_invalidates_clock_and_date_widget_cache(client, tmp_db):
    from app.storage.cache import cache

    cache.set("summary:clock:en", {"timezone": "UTC"}, 3600)
    cache.set("detail:clock:en", {"timezone": "UTC"}, 3600)
    cache.set("summary:date:en", {"timezone": "UTC"}, 3600)
    cache.set("detail:date:en", {"timezone": "UTC"}, 3600)

    client.patch("/api/settings", json={"timezone": "America/New_York"})

    assert cache.get("summary:clock:en") is None
    assert cache.get("detail:clock:en") is None
    assert cache.get("summary:date:en") is None
    assert cache.get("detail:date:en") is None


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


def test_patch_settings_rejects_searxng_url_without_http_or_https(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={"searxng_url": "searxng.local:8080"},
    )
    assert response.status_code == 422
    assert "SearXNG URL must start with http:// or https://" in response.text

    response_ftp = client.patch(
        "/api/settings",
        json={"searxng_url": "ftp://searxng.local:8080"},
    )
    assert response_ftp.status_code == 422
    assert "SearXNG URL must start with http:// or https://" in response_ftp.text


def test_patch_settings_accepts_https_and_clearing_searxng_url(client, tmp_db):
    res_https = client.patch("/api/settings", json={"searxng_url": "https://searxng.secure:8443"})
    assert res_https.status_code == 200
    assert res_https.json()["searxng_url"] == "https://searxng.secure:8443"

    res_clear = client.patch("/api/settings", json={"searxng_url": ""})
    assert res_clear.status_code == 200
    assert res_clear.json()["searxng_url"] == ""


def test_patch_settings_tmdb_api_key_and_discord_bot_token(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={
            "tmdb_api_key": "tmdb-secret-key",
            "discord_bot_token": "discord-secret-token",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "tmdb_api_key" not in body
    assert "discord_bot_token" not in body
    assert body["has_tmdb_api_key"] is True
    assert body["has_discord_bot_token"] is True


def test_patch_settings_clearing_tmdb_and_discord(client, tmp_db):
    client.patch(
        "/api/settings",
        json={
            "tmdb_api_key": "tmdb-secret-key",
            "discord_bot_token": "discord-secret-token",
        },
    )
    response = client.patch(
        "/api/settings",
        json={
            "tmdb_api_key": "",
            "discord_bot_token": "",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_tmdb_api_key"] is False
    assert body["has_discord_bot_token"] is False


def test_patch_settings_artificial_analysis_api_key(client, tmp_db):
    response = client.patch(
        "/api/settings",
        json={"artificial_analysis_api_key": "aa-secret-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "artificial_analysis_api_key" not in body
    assert body["has_artificial_analysis_api_key"] is True


def test_patch_settings_clearing_artificial_analysis_api_key(client, tmp_db):
    client.patch("/api/settings", json={"artificial_analysis_api_key": "aa-secret-key"})
    response = client.patch("/api/settings", json={"artificial_analysis_api_key": ""})
    assert response.status_code == 200
    assert response.json()["has_artificial_analysis_api_key"] is False


def test_patch_settings_invalidates_artificial_analysis_cache(client, tmp_db):
    from app.storage.cache import cache

    cache.set("summary:artificial_analysis:en", {"data": 1}, 3600)
    cache.set("detail:artificial_analysis:en", {"data": 2}, 3600)

    client.patch("/api/settings", json={"artificial_analysis_api_key": "new-key"})

    assert cache.get("summary:artificial_analysis:en") is None
    assert cache.get("detail:artificial_analysis:en") is None


def test_patch_settings_invalidates_movies_and_discord_cache(client, tmp_db):
    from app.storage.cache import cache

    cache.set("summary:movies:en", {"data": 1}, 3600)
    cache.set("detail:movies:en", {"data": 2}, 3600)
    cache.set("movies:providers:US:movie:123", {"data": 3}, 3600)
    cache.set("summary:discord:en", {"data": 4}, 3600)
    cache.set("detail:discord:en", {"data": 5}, 3600)

    client.patch("/api/settings", json={"tmdb_api_key": "new-key", "discord_bot_token": "new-token"})

    assert cache.get("summary:movies:en") is None
    assert cache.get("detail:movies:en") is None
    assert cache.get("movies:providers:US:movie:123") is None
    assert cache.get("summary:discord:en") is None
    assert cache.get("detail:discord:en") is None
