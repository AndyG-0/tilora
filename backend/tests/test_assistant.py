from __future__ import annotations

import pytest

from app import config
from app.ai import assistant
from app.storage.db import save_app_settings


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
