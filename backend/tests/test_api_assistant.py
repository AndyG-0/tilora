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


def test_topics_returns_visible_widgets_with_location_names(client, tmp_db, monkeypatch):
    from app.plugins.base import registry
    from app.plugins.sports.plugin import SportsPlugin
    from app.plugins.weather.plugin import WeatherPlugin

    registry._plugins.clear()
    registry.register(WeatherPlugin({"id": "weather", "settings": {"location_name": "Chicago, IL"}}))
    registry.register(SportsPlugin({"id": "sports", "settings": {}}))

    monkeypatch.setattr(
        assistant_api,
        "load_dashboard_config",
        lambda: {
            "widgets": [
                {"id": "weather", "type": "weather", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
                {"id": "sports", "type": "sports", "layout": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}},
            ]
        },
    )

    response = client.get("/api/assistant/topics")
    assert response.status_code == 200
    topics = response.json()
    assert topics == [
        {"id": "weather", "name": "Weather (Chicago, IL)"},
        {"id": "sports", "name": "Sports Schedule"},
    ]


def test_topics_excludes_hidden_widgets(client, tmp_db, monkeypatch):
    from app.plugins.base import registry
    from app.plugins.weather.plugin import WeatherPlugin
    from app.storage import db

    registry._plugins.clear()
    registry.register(WeatherPlugin({"id": "weather", "settings": {"location_name": "Chicago, IL"}}))
    registry.register(WeatherPlugin({"id": "weather-custom", "settings": {"location_name": "London, UK"}}))

    db.hide_widget(TEST_USER_ID, TEST_DEVICE_ID, "weather")

    monkeypatch.setattr(
        assistant_api,
        "load_dashboard_config",
        lambda: {
            "widgets": [
                {"id": "weather", "type": "weather", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
                {"id": "weather-custom", "type": "weather", "layout": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}},
            ]
        },
    )

    response = client.get("/api/assistant/topics")
    assert response.status_code == 200
    topics = response.json()
    # "weather" was hidden on this device, so only "weather-custom" appears
    assert topics == [
        {"id": "weather-custom", "name": "Weather (London, UK)"},
    ]
