from __future__ import annotations

import litellm
import pytest

from app.ai.provider import AIProvider, _api_key_for_model
from app.ai.tools import ToolBridge
from app.plugins.base import ToolDef


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self):
        return {"role": "assistant", "content": self.content, "tool_calls": self.tool_calls}


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


def empty_bridge() -> ToolBridge:
    return ToolBridge([])


async def test_run_prompt_returns_content_when_no_tool_calls(monkeypatch, tmp_db):
    async def fake_acompletion(**kwargs):
        return FakeResponse(FakeMessage(content="Hello there"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(empty_bridge(), model="fake/model")
    result = await provider.run_prompt("Say hi")

    assert result == "Hello there"


async def test_run_prompt_calls_tool_then_returns_final_answer(monkeypatch, tmp_db):
    calls = []

    async def handler(city: str) -> dict:
        return {"temp": 72, "city": city}

    tool = ToolDef(
        name="get_weather",
        description="d",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        handler=handler,
    )
    bridge = ToolBridge([tool])

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            tool_call = FakeToolCall("call_1", "get_weather", '{"city": "Austin"}')
            return FakeResponse(FakeMessage(tool_calls=[tool_call]))
        return FakeResponse(FakeMessage(content="It's 72 in Austin"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(bridge, model="fake/model")
    result = await provider.run_prompt("What's the weather?")

    assert result == "It's 72 in Austin"
    assert len(calls) == 2
    # second call's message list should include the tool result
    tool_messages = [m for m in calls[1]["messages"] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "Austin" in tool_messages[0]["content"]


async def test_run_prompt_forces_final_answer_after_max_rounds(monkeypatch, tmp_db):
    call_count = 0

    async def handler() -> dict:
        return {"ok": True}

    tool = ToolDef(name="noop", description="d", parameters={"type": "object"}, handler=handler)
    bridge = ToolBridge([tool])
    tool_call = FakeToolCall("call_1", "noop", "{}")

    async def fake_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("tools"):
            return FakeResponse(FakeMessage(tool_calls=[tool_call]))
        return FakeResponse(FakeMessage(content="giving up, here's what I know"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(bridge, model="fake/model")
    result = await provider.run_prompt("loop forever", max_tool_rounds=2)

    assert result == "giving up, here's what I know"
    assert call_count == 3  # 2 tool rounds + 1 final forced call without tools


@pytest.mark.parametrize(
    "model,expected_key",
    [
        ("anthropic/claude-sonnet-5", "sk-anthropic"),
        ("openai/gpt-5", "sk-openai"),
        ("gemini/gemini-2.5-flash", "sk-gemini"),
    ],
)
def test_api_key_for_model_picks_key_matching_provider_prefix(model, expected_key):
    settings = {
        "anthropic_api_key": "sk-anthropic",
        "openai_api_key": "sk-openai",
        "gemini_api_key": "sk-gemini",
    }

    assert _api_key_for_model(model, settings) == expected_key


def test_api_key_for_model_falls_back_when_prefix_unknown_or_unset():
    settings = {"anthropic_api_key": None, "openai_api_key": "sk-openai", "gemini_api_key": None}

    assert _api_key_for_model("fake/model", settings) == "sk-openai"
    assert _api_key_for_model("gemini/gemini-2.5-flash", settings) == "sk-openai"


async def test_run_prompt_passes_provider_matched_key_to_litellm(monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return FakeResponse(FakeMessage(content="ok"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        "app.ai.provider.effective_settings",
        lambda: {
            "ai_model": "gemini/gemini-2.5-flash",
            "anthropic_api_key": None,
            "openai_api_key": None,
            "gemini_api_key": "sk-gemini",
        },
    )

    provider = AIProvider(empty_bridge(), model="gemini/gemini-2.5-flash")
    await provider.run_prompt("hi")

    assert captured["api_key"] == "sk-gemini"
