from __future__ import annotations

import pytest

from app import config
from app.ai import assistant


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


async def test_ask_passes_system_prompt_through_to_provider(monkeypatch, tmp_db, dashboard_yaml):
    captured = {}

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        captured["system_prompt"] = system_prompt
        return "ok"

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await assistant.ask("hi", system_prompt="Answer briefly.")

    assert captured["system_prompt"] == "Answer briefly."
