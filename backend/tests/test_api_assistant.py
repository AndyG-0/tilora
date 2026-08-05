from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import assistant as assistant_api
from app.auth import get_current_device, get_current_user

TEST_USER_ID = "test-user"
TEST_DEVICE_ID = "test-device"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(assistant_api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "role": "member"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
    return TestClient(app)


def test_ask_returns_answer(client, tmp_db, monkeypatch):
    async def fake_ask(text, system_prompt=None, user=None, device=None):
        assert text == "What's the weather?"
        assert user == {"id": TEST_USER_ID, "role": "member"}
        assert device == {"id": TEST_DEVICE_ID}
        return "Sunny and 75."

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 200
    assert response.json() == {"text": "Sunny and 75."}


def test_ask_passes_speech_system_prompt(client, tmp_db, monkeypatch):
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None):
        captured["system_prompt"] = system_prompt
        return "Sunny and 75."

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert captured["system_prompt"]


def test_ask_rejects_empty_text(client, tmp_db):
    response = client.post("/api/assistant/ask", json={"text": "   "})

    assert response.status_code == 400


def test_ask_rejects_missing_text(client, tmp_db):
    response = client.post("/api/assistant/ask", json={})

    assert response.status_code == 400
