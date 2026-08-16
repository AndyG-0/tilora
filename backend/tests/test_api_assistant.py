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


def test_ask_returns_502_and_logs_when_assistant_raises(client, tmp_db, monkeypatch, caplog):
    async def fake_ask(text, system_prompt=None, user=None, device=None):
        raise RuntimeError("Request too large for gpt-5.6-luna: tokens per min (TPM) exceeded")

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    with caplog.at_level("ERROR"):
        response = client.post("/api/assistant/ask", json={"text": "get me directions to taco bell"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI assistant is unavailable right now."}
    assert "Assistant request failed" in caplog.text


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


def test_topics_disambiguates_same_location_with_stable_suffix(client, tmp_db, monkeypatch):
    from app.plugins.base import registry
    from app.plugins.weather.plugin import WeatherPlugin

    registry._plugins.clear()
    registry.register(WeatherPlugin({"id": "weather-b", "settings": {"location_name": "Chicago, IL"}}))
    registry.register(WeatherPlugin({"id": "weather-a", "settings": {"location_name": "Chicago, IL"}}))

    monkeypatch.setattr(
        assistant_api,
        "load_dashboard_config",
        lambda: {
            "widgets": [
                {"id": "weather-b", "type": "weather", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
                {"id": "weather-a", "type": "weather", "layout": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}},
            ]
        },
    )

    response = client.get("/api/assistant/topics")
    assert response.status_code == 200
    topics = {t["id"]: t["name"] for t in response.json()}
    # Suffix ordering is id-sorted (stable across requests), not config/list order.
    assert topics == {
        "weather-a": "Weather (Chicago, IL)",
        "weather-b": "Weather (Chicago, IL) (2)",
    }


def test_topics_uses_custom_name_override(client, tmp_db, monkeypatch):
    from app.plugins.base import registry
    from app.plugins.weather.plugin import WeatherPlugin
    from app.storage import db

    registry._plugins.clear()
    registry.register(WeatherPlugin({"id": "weather", "settings": {"location_name": "Chicago, IL"}}))
    db.save_widget_custom_name("weather", "Home")

    monkeypatch.setattr(
        assistant_api,
        "load_dashboard_config",
        lambda: {
            "widgets": [
                {"id": "weather", "type": "weather", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
            ]
        },
    )

    response = client.get("/api/assistant/topics")
    assert response.status_code == 200
    assert response.json() == [{"id": "weather", "name": "Home"}]
