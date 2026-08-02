from __future__ import annotations

from app.ai import assistant


async def test_ask_returns_provider_result(monkeypatch, tmp_db):
    async def fake_run_prompt(self, prompt, max_tool_rounds=4):
        assert prompt == "What's the weather?"
        return "Sunny and 75."

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    result = await assistant.ask("What's the weather?")

    assert result == "Sunny and 75."
