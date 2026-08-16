from __future__ import annotations

import litellm
import pytest

from app.ai.provider import _MAX_COMPLETION_TOKENS, AIProvider, _api_key_for_model
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


async def test_run_prompt_prepends_system_prompt_when_given(monkeypatch, tmp_db):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return FakeResponse(FakeMessage(content="ok"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(empty_bridge(), model="fake/model")
    await provider.run_prompt("hi", system_prompt="Answer briefly.")

    assert captured["messages"][0] == {"role": "system", "content": "Answer briefly."}
    assert captured["messages"][1] == {"role": "user", "content": "hi"}


async def test_run_prompt_omits_system_message_when_not_given(monkeypatch, tmp_db):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return FakeResponse(FakeMessage(content="ok"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(empty_bridge(), model="fake/model")
    await provider.run_prompt("hi")

    assert captured["messages"] == [{"role": "user", "content": "hi"}]


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
    # every call caps output tokens, so a single request never gets rate-limited
    # by a provider reserving an unbounded amount of headroom for the reply
    assert all(call["max_completion_tokens"] == _MAX_COMPLETION_TOKENS for call in calls)


async def test_run_prompt_surfaces_tool_handler_exception_instead_of_raising(monkeypatch, tmp_db):
    async def handler(city: str) -> dict:
        raise RuntimeError("network unreachable")

    tool = ToolDef(
        name="get_weather",
        description="d",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        handler=handler,
    )
    bridge = ToolBridge([tool])
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            tool_call = FakeToolCall("call_1", "get_weather", '{"city": "Austin"}')
            return FakeResponse(FakeMessage(tool_calls=[tool_call]))
        return FakeResponse(FakeMessage(content="Couldn't check the weather"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(bridge, model="fake/model")
    result = await provider.run_prompt("What's the weather?")

    assert result == "Couldn't check the weather"
    tool_messages = [m for m in calls[1]["messages"] if m.get("role") == "tool"]
    assert "network unreachable" in tool_messages[0]["content"]


async def test_run_prompt_forces_final_answer_after_max_rounds(monkeypatch, tmp_db):
    calls = []

    async def handler() -> dict:
        return {"ok": True}

    tool = ToolDef(name="noop", description="d", parameters={"type": "object"}, handler=handler)
    bridge = ToolBridge([tool])
    tool_call = FakeToolCall("call_1", "noop", "{}")

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tools"):
            return FakeResponse(FakeMessage(tool_calls=[tool_call]))
        return FakeResponse(FakeMessage(content="giving up, here's what I know"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    provider = AIProvider(bridge, model="fake/model")
    result = await provider.run_prompt("loop forever", max_tool_rounds=2)

    assert result == "giving up, here's what I know"
    assert len(calls) == 3  # 2 tool rounds + 1 final forced call without tools
    # the forced final call (no tools) still caps output tokens, same as the
    # tool-loop calls before it
    assert calls[-1]["max_completion_tokens"] == _MAX_COMPLETION_TOKENS


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


def test_api_key_for_model_falls_back_to_any_key_for_unknown_prefix():
    settings = {"anthropic_api_key": None, "openai_api_key": "sk-openai", "gemini_api_key": None}

    assert _api_key_for_model("fake/model", settings) == "sk-openai"


def test_api_key_for_model_does_not_borrow_another_providers_key():
    # A known provider with its own key unset must not silently use a
    # different provider's key — that key would get sent to the wrong API.
    settings = {"anthropic_api_key": None, "openai_api_key": "sk-openai", "gemini_api_key": None}

    assert _api_key_for_model("gemini/gemini-2.5-flash", settings) is None


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


async def test_run_prompt_omits_reasoning_effort_when_not_configured(monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return FakeResponse(FakeMessage(content="ok"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        "app.ai.provider.effective_settings",
        lambda: {"ai_model": "openai/gpt-5.6-luna", "openai_api_key": "sk-openai", "ai_reasoning_effort": None},
    )

    provider = AIProvider(empty_bridge(), model="openai/gpt-5.6-luna")
    await provider.run_prompt("hi")

    assert "reasoning_effort" not in captured
    assert "drop_params" not in captured


async def test_run_prompt_passes_configured_reasoning_effort_to_litellm(monkeypatch):
    calls = []

    async def handler() -> dict:
        return {"ok": True}

    tool = ToolDef(name="noop", description="d", parameters={"type": "object"}, handler=handler)
    bridge = ToolBridge([tool])
    tool_call = FakeToolCall("call_1", "noop", "{}")

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tools"):
            return FakeResponse(FakeMessage(tool_calls=[tool_call]))
        return FakeResponse(FakeMessage(content="done"))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        "app.ai.provider.effective_settings",
        lambda: {"ai_model": "openai/gpt-5.6-terra", "openai_api_key": "sk-openai", "ai_reasoning_effort": "none"},
    )

    provider = AIProvider(bridge, model="openai/gpt-5.6-terra")
    result = await provider.run_prompt("do the thing", max_tool_rounds=1)

    assert result == "done"
    assert len(calls) == 2  # 1 tool round (forces final since max_tool_rounds=1) + 1 forced final call
    for call in calls:
        assert call["reasoning_effort"] == "none"
        assert call["drop_params"] is True
