"""Shared entry point for running a prompt through the tool-calling loop.

Both the scheduled AI widgets (`app.scheduler.run_ai_widget`) and the ad-hoc
voice/text assistant (`POST /api/assistant/ask`) need the same MCP + local
tool wiring — this is the one place that assembles it.
"""

from __future__ import annotations

from app.ai.mcp_client import MCPToolSource, load_mcp_server_configs
from app.ai.provider import AIProvider
from app.ai.tools import ToolBridge
from app.plugins.base import registry


async def ask(text: str) -> str:
    # MCP servers (if any are configured) are connected fresh for each call
    # and torn down afterwards — tools from local plugins and MCP servers are
    # merged into one bridge, so the model can't tell (or needs to care)
    # where a given tool came from.
    async with MCPToolSource(load_mcp_server_configs()) as mcp_source:
        tools = registry.all_tools() + await mcp_source.tools()
        provider = AIProvider(ToolBridge(tools))
        return await provider.run_prompt(text)
