from __future__ import annotations

import pytest

from app import config
from app.ai import assistant
from app.storage.db import save_app_settings, save_user_preferences


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text("widgets: []\n")
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)
    return path


async def test_ask_returns_provider_result(monkeypatch, tmp_db, dashboard_yaml):
    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        assert prompt == "What's the weather?"
        return "Sunny and 75."

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    result = await assistant.ask("What's the weather?")

    assert result == "Sunny and 75."


async def test_ask_passes_system_prompt_with_date_and_identity(monkeypatch, tmp_db, dashboard_yaml):
    captured = {}

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("hi", system_prompt="Answer briefly.")

    sys_prompt = captured["system_prompt"]
    assert "You are Tilora" in sys_prompt
    assert "Current date and time:" in sys_prompt
    assert "Answer briefly." in sys_prompt


async def test_ask_uses_custom_agent_name(monkeypatch, tmp_db, dashboard_yaml):
    save_app_settings({"ai_agent_name": "Jarvis"})
    captured = {}

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("hi")

    sys_prompt = captured["system_prompt"]
    assert "You are Jarvis" in sys_prompt


async def test_ask_appends_user_location_to_system_prompt(monkeypatch, tmp_db, dashboard_yaml):
    save_user_preferences(
        "user-1",
        {
            "location": {
                "query": "Fort Worth",
                "display_name": "Fort Worth, TX",
                "latitude": 32.7555,
                "longitude": -97.3308,
            }
        },
    )
    captured = {}

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("hi", user={"id": "user-1"}, device={"id": "device-1"})

    sys_prompt = captured["system_prompt"]
    assert "Fort Worth, TX" in sys_prompt
    assert "32.7555" in sys_prompt
    assert "-97.3308" in sys_prompt


async def test_ask_omits_location_line_when_unset(monkeypatch, tmp_db, dashboard_yaml):
    captured = {}

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("hi", user={"id": "user-1"}, device={"id": "device-1"})

    assert "location is" not in captured["system_prompt"]


async def test_ask_omits_location_when_no_user(monkeypatch, tmp_db, dashboard_yaml):
    captured = {}

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("hi")

    assert "location is" not in captured["system_prompt"]


async def test_ask_registers_web_tools_when_searxng_url_configured(monkeypatch, tmp_db, dashboard_yaml):
    save_app_settings({"searxng_url": "http://searxng.internal:8080"})
    captured = {}

    def fake_init(self, tool_bridge, model=None):
        captured["tool_names"] = list(tool_bridge._tools.keys())
        self._tools = tool_bridge
        self._model = "test-model"

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.__init__", fake_init)
    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("search the web")

    assert "web_search" in captured["tool_names"]
    assert "web_fetch" in captured["tool_names"]


async def test_ask_omits_web_tools_when_searxng_url_not_configured(monkeypatch, tmp_db, dashboard_yaml):
    captured = {}

    def fake_init(self, tool_bridge, model=None):
        captured["tool_names"] = list(tool_bridge._tools.keys())
        self._tools = tool_bridge
        self._model = "test-model"

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.__init__", fake_init)
    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("no web search")

    assert "web_search" not in captured["tool_names"]
    assert "web_fetch" not in captured["tool_names"]
