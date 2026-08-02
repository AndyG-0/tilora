from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import assistant as assistant_api


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(assistant_api.router)
    return TestClient(app)


def test_ask_returns_answer(client, tmp_db, monkeypatch):
    async def fake_ask(text):
        assert text == "What's the weather?"
        return "Sunny and 75."

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 200
    assert response.json() == {"text": "Sunny and 75."}


def test_ask_rejects_empty_text(client, tmp_db):
    response = client.post("/api/assistant/ask", json={"text": "   "})

    assert response.status_code == 400


def test_ask_rejects_missing_text(client, tmp_db):
    response = client.post("/api/assistant/ask", json={})

    assert response.status_code == 400
