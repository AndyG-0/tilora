"""MCP client integration.

Converts tools exposed by external MCP servers into the same `ToolDef` shape
local plugins use (`app.plugins.base.ToolDef`), so `ToolBridge`/`AIProvider`
never need to know whether a tool came from a local plugin or a remote MCP
server — see `app.ai.tools.ToolBridge`'s docstring for the intended seam.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool as MCPTool

from app.config import load_dashboard_config
from app.plugins.base import ToolDef


@dataclass(frozen=True)
class MCPServerConfig:
    """One configured MCP server.

    Set `command` (+ optional `args`/`env`) to launch a local server over
    stdio, or `url` to connect to a remote server over streamable HTTP.
    """

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    url: str | None = None


def load_mcp_server_configs() -> list[MCPServerConfig]:
    config = load_dashboard_config()
    return [
        MCPServerConfig(
            name=server["name"],
            command=server.get("command"),
            args=server.get("args", []),
            env=server.get("env"),
            url=server.get("url"),
        )
        for server in config.get("mcp_servers", [])
    ]


def _tool_def(session: ClientSession, tool: MCPTool) -> ToolDef:
    async def handler(**kwargs: Any) -> Any:
        result = await session.call_tool(tool.name, kwargs)
        texts = [block.text for block in result.content if block.type == "text"]
        if texts:
            return "\n".join(texts)
        return [block.model_dump() for block in result.content]

    return ToolDef(
        name=tool.name,
        description=tool.description or "",
        parameters=tool.inputSchema,
        handler=handler,
    )


class MCPToolSource:
    """Owns live sessions to all configured MCP servers for one AI run.

    Sessions are only meant to live for the duration of a single prompt run
    (e.g. one scheduled AI widget execution) — use as an async context
    manager so every connection is torn down cleanly afterwards:

        async with MCPToolSource(load_mcp_server_configs()) as source:
            tools = await source.tools()
            ...
    """

    def __init__(self, servers: list[MCPServerConfig]):
        self._servers = servers
        self._stack = AsyncExitStack()
        self._sessions: list[ClientSession] = []

    async def __aenter__(self) -> MCPToolSource:
        await self._stack.__aenter__()
        for server in self._servers:
            self._sessions.append(await self._connect(server))
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._stack.__aexit__(*exc_info)

    async def _connect(self, server: MCPServerConfig) -> ClientSession:
        if server.url:
            read, write, _ = await self._stack.enter_async_context(streamablehttp_client(server.url))
        elif server.command:
            params = StdioServerParameters(command=server.command, args=server.args, env=server.env)
            read, write = await self._stack.enter_async_context(stdio_client(params))
        else:
            raise ValueError(f"MCP server '{server.name}' needs either `command` or `url`")

        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    async def tools(self) -> list[ToolDef]:
        tool_defs: list[ToolDef] = []
        for session in self._sessions:
            result = await session.list_tools()
            tool_defs.extend(_tool_def(session, tool) for tool in result.tools)
        return tool_defs
