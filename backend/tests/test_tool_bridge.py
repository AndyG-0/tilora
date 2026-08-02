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
