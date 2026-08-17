from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.provider import PromptResult
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


@pytest.fixture(autouse=True)
def _stub_dashboard_config(monkeypatch):
    # Visible-topic resolution in POST /ask and GET /topics loads dashboard.yaml
    # to find configured widgets. Default to empty widgets so tests don't depend
    # on the deployment-specific (and gitignored) dashboard.yaml file existing on disk.
    monkeypatch.setattr(assistant_api, "load_dashboard_config", lambda: {"widgets": []})


@pytest.fixture(autouse=True)
def _stub_router(monkeypatch):
    # POST /ask now runs a tool-selection router pass before assistant.ask --
    # stub it to "don't restrict" (today's pre-router behavior) by default so
    # existing tests don't need to know about it; tests that care about the
    # router's effect override this within the test body.
    async def fake_select_relevant_topics(text, topics, model=None):
        return None

    monkeypatch.setattr(assistant_api, "select_relevant_topics", fake_select_relevant_topics)


def test_ask_returns_answer(client, tmp_db, monkeypatch):
    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        assert text == "What's the weather?"
        assert user == {"id": TEST_USER_ID, "role": "member"}
        assert device == {"id": TEST_DEVICE_ID}
        return PromptResult("Sunny and 75.")

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 200
    assert response.json() == {"text": "Sunny and 75.", "action": None}


def test_ask_returns_navigation_action_when_present(client, tmp_db, monkeypatch):
    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        return PromptResult("Here's the weather.", {"widget_id": "weather", "panel": None})

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 200
    assert response.json() == {"text": "Here's the weather.", "action": {"widget_id": "weather", "panel": None}}


def test_ask_forwards_router_selection_as_allowed_widget_ids(client, tmp_db, monkeypatch):
    captured = {}

    async def fake_select_relevant_topics(text, topics, model=None):
        assert text == "What's the weather?"
        return ["weather"]

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["allowed_widget_ids"] = allowed_widget_ids
        return PromptResult("Sunny and 75.")

    monkeypatch.setattr(assistant_api, "select_relevant_topics", fake_select_relevant_topics)
    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 200
    assert captured["allowed_widget_ids"] == ["weather"]


def test_ask_leaves_tools_unrestricted_when_router_returns_none(client, tmp_db, monkeypatch):
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["allowed_widget_ids"] = allowed_widget_ids
        return PromptResult("42")

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "what is 2+2"})

    assert response.status_code == 200
    assert captured["allowed_widget_ids"] is None


def test_ask_passes_speech_system_prompt(client, tmp_db, monkeypatch):
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["system_prompt"] = system_prompt
        return PromptResult("Sunny and 75.")

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert captured["system_prompt"]


def test_ask_returns_502_and_logs_when_assistant_raises(client, tmp_db, monkeypatch, caplog):
    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        raise RuntimeError("Request too large for gpt-5.6-luna: tokens per min (TPM) exceeded")

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    with caplog.at_level("ERROR"):
        response = client.post("/api/assistant/ask", json={"text": "get me directions to taco bell"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI assistant is unavailable right now."}
    assert "Assistant request failed" in caplog.text


class _FakeRateLimitError(Exception):
    """Mimics the attributes app.api.assistant._rate_limit_retry_seconds reads
    off litellm.RateLimitError, without importing litellm in tests."""

    def __init__(self, message: str, response=None):
        super().__init__(message)
        self.status_code = 429
        self.response = response


class _FakeResponse:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


def test_ask_returns_429_with_retry_seconds_from_message(client, tmp_db, monkeypatch, caplog):
    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        raise _FakeRateLimitError(
            "litellm.RateLimitError: RateLimitError: OpenAIException - Rate limit reached for gpt-5.6-luna "
            "on tokens per min (TPM): Limit 200000, Used 111254, Requested 122603. Please try again in 10.157s."
        )

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    with caplog.at_level("ERROR"):
        response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 429
    assert response.json() == {
        "detail": "The AI assistant is getting too many requests right now — try again in about 10 seconds."
    }


def test_ask_returns_429_with_retry_seconds_from_retry_after_header(client, tmp_db, monkeypatch):
    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        raise _FakeRateLimitError("rate limited", response=_FakeResponse({"retry-after": "3"}))

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 429
    assert response.json() == {
        "detail": "The AI assistant is getting too many requests right now — try again in about 3 seconds."
    }


def test_ask_returns_429_without_retry_seconds_when_unknown(client, tmp_db, monkeypatch):
    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        raise _FakeRateLimitError("rate limited, no timing info given")

    monkeypatch.setattr(assistant_api.assistant, "ask", fake_ask)

    response = client.post("/api/assistant/ask", json={"text": "What's the weather?"})

    assert response.status_code == 429
    assert response.json() == {
        "detail": "The AI assistant is getting too many requests right now — try again in a moment."
    }


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


def test_config_returns_default_agent_name(client, tmp_db):
    response = client.get("/api/assistant/config")
    assert response.status_code == 200
    assert response.json() == {"agent_name": "Tilora"}


def test_config_returns_custom_agent_name(client, tmp_db):
    from app.storage import db

    db.save_app_settings({"ai_agent_name": "Jarvis"})

    response = client.get("/api/assistant/config")
    assert response.status_code == 200
    assert response.json() == {"agent_name": "Jarvis"}
