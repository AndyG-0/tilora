from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import tts as tts_api
from app.auth import _hash_token
from app.storage import db


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(tts_api.router)
    return TestClient(app)


def _login(client, user_id="alice", device_id="tablet"):
    # devices/sessions are keyed by a hash of the bearer token — store the
    # hash, present the raw value as the cookie (see app.auth._hash_token).
    db.create_user(user_id, "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_device(_hash_token(device_id), "Tablet", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    db.create_session(
        _hash_token("sess1"), user_id, _hash_token(device_id), "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z"
    )
    client.cookies.set("tilora_session", "sess1")
    client.cookies.set("tilora_device", device_id)


def test_voices_requires_a_user_session(client, tmp_db):
    response = client.get("/api/tts/voices")

    assert response.status_code == 401


def test_voices_empty_when_nothing_enabled(client, tmp_db):
    _login(client)

    response = client.get("/api/tts/voices")

    assert response.status_code == 200
    assert response.json() == []


def test_voices_populates_once_openai_tts_is_enabled(client, tmp_db):
    _login(client)
    db.save_app_settings({"openai_tts_enabled": "true", "openai_api_key": "sk-openai"})

    response = client.get("/api/tts/voices")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 9
    assert all(v["provider"] == "openai" for v in body)


def test_voices_populates_once_piper_tts_is_enabled(client, tmp_db):
    _login(client)
    db.save_app_settings(
        {
            "piper_tts_enabled": "true",
            "piper_server_url": "http://piper.local:5000",
            "piper_voices": "en_US-amy-medium|Amy",
        }
    )

    response = client.get("/api/tts/voices")

    assert response.status_code == 200
    assert response.json() == [{"id": "en_US-amy-medium", "label": "Amy", "provider": "piper"}]


def test_synthesize_requires_a_user_session(client, tmp_db):
    response = client.post("/api/tts/synthesize", json={"provider": "openai", "voice_id": "nova", "text": "hi"})

    assert response.status_code == 401


def test_synthesize_400s_for_disabled_provider(client, tmp_db):
    _login(client)

    response = client.post("/api/tts/synthesize", json={"provider": "openai", "voice_id": "nova", "text": "hi"})

    assert response.status_code == 400


def test_synthesize_400s_for_unknown_voice(client, tmp_db):
    _login(client)
    db.save_app_settings({"openai_tts_enabled": "true", "openai_api_key": "sk-openai"})

    response = client.post("/api/tts/synthesize", json={"provider": "openai", "voice_id": "not-a-voice", "text": "hi"})

    assert response.status_code == 400


def test_synthesize_200s_with_expected_media_type(client, tmp_db, monkeypatch):
    _login(client)
    db.save_app_settings({"openai_tts_enabled": "true", "openai_api_key": "sk-openai"})

    async def fake_synthesize(text, voice_id, settings):
        return b"fake-mp3-bytes"

    monkeypatch.setattr("app.tts.openai_tts.synthesize", fake_synthesize)

    response = client.post("/api/tts/synthesize", json={"provider": "openai", "voice_id": "nova", "text": "hi"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3-bytes"


def test_synthesize_rejects_text_over_max_length(client, tmp_db):
    _login(client)
    db.save_app_settings({"openai_tts_enabled": "true", "openai_api_key": "sk-openai"})

    response = client.post("/api/tts/synthesize", json={"provider": "openai", "voice_id": "nova", "text": "x" * 1001})

    assert response.status_code == 422
