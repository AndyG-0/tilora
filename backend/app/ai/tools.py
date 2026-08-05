"""Bridges plugin-exposed ToolDefs to the LLM function-calling schema.

This is the seam where real MCP support gets added later (see TODO.md):
`ToolDef` is a plain, provider-agnostic dict-shaped definition, so a future
`ToolBridge` could source tools from an MCP client instead of local plugin
instances without changing how `AIProvider` consumes them.
"""

from __future__ import annotations

from typing import Any

from app.plugins.base import ToolDef


class ToolBridge:
    def __init__(self, tools: list[ToolDef]):
        self._tools = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    async def call(self, name: str, args: dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool '{name}'"}
        try:
            return await tool.handler(**args)
        except Exception as exc:
            # Surfaced to the model as a tool result instead of raised, so one
            # flaky handler (e.g. a transient network error) doesn't 500 the
            # whole response — the model can explain the failure instead.
            return {"error": str(exc)}
