from __future__ import annotations

from app.ai.tools import ToolBridge
from app.plugins.base import ToolDef


async def _add(a: int, b: int) -> int:
    return a + b


def make_bridge() -> ToolBridge:
    tool = ToolDef(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        handler=_add,
    )
    return ToolBridge([tool])


def test_schemas_shape_matches_llm_tool_calling_format():
    bridge = make_bridge()
    schemas = bridge.schemas()
    assert schemas == [
        {
            "type": "function",
            "function": {
                "name": "add",
                "description": "Add two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            },
        }
    ]


async def test_call_invokes_matching_handler():
    bridge = make_bridge()
    result = await bridge.call("add", {"a": 2, "b": 3})
    assert result == 5


async def test_call_unknown_tool_returns_error_dict():
    bridge = make_bridge()
    result = await bridge.call("nonexistent", {})
    assert result == {"error": "Unknown tool 'nonexistent'"}


async def _navigate() -> dict:
    return {"widget_id": "weather", "panel": None}


def make_navigation_bridge(handler=_navigate) -> ToolBridge:
    tool = ToolDef(
        name="show_weather_detail",
        description="Show weather detail",
        parameters={"type": "object", "properties": {}},
        handler=handler,
        is_navigation=True,
    )
    return ToolBridge([tool])


async def test_call_navigation_tool_sets_navigation_action_on_success():
    bridge = make_navigation_bridge()
    result = await bridge.call("show_weather_detail", {})
    assert result == {"widget_id": "weather", "panel": None}
    assert bridge.navigation_action == {"widget_id": "weather", "panel": None}


async def test_call_navigation_tool_clears_navigation_action_on_error():
    async def handler():
        raise RuntimeError("boom")

    bridge = make_navigation_bridge(handler)
    result = await bridge.call("show_weather_detail", {})
    assert result == {"error": "boom"}
    assert bridge.navigation_action is None


async def test_call_navigation_tool_ignores_result_missing_widget_id():
    async def handler():
        return {"panel": None}

    bridge = make_navigation_bridge(handler)
    await bridge.call("show_weather_detail", {})
    assert bridge.navigation_action is None


async def test_call_navigation_action_reflects_most_recent_call():
    calls = iter([{"widget_id": "weather", "panel": None}, {"error": "boom"}])

    async def handler():
        return next(calls)

    bridge = make_navigation_bridge(handler)
    await bridge.call("show_weather_detail", {})
    assert bridge.navigation_action == {"widget_id": "weather", "panel": None}

    await bridge.call("show_weather_detail", {})
    assert bridge.navigation_action is None
