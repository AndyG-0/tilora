"""Shared entry point for running a prompt through the tool-calling loop.

Both the scheduled AI widgets (`app.scheduler.run_ai_widget`) and the ad-hoc
voice/text assistant (`POST /api/assistant/ask`) need the same MCP + local
tool wiring — this is the one place that assembles it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.ai.mcp_client import MCPToolSource, load_mcp_server_configs
from app.ai.provider import AIProvider
from app.ai.tools import ToolBridge
from app.ai.web_tools import get_web_tools
from app.config import effective_settings, resolve_timezone
from app.plugins.base import registry
from app.plugins.scoping import scoped_plugin


def _build_system_prompt(system_prompt: str | None = None) -> str:
    settings = effective_settings()
    agent_name = (settings.get("ai_agent_name") or "").strip() or "Tilora"
    tz_name = settings.get("timezone") or "UTC"
    tz = resolve_timezone(tz_name)
    now = datetime.now(tz)
    now_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
    parts = [
        f"You are {agent_name}, a helpful AI assistant for the Tilora smart dashboard.",
        f"Current date and time: {now_str} ({tz_name}).",
    ]
    if system_prompt:
        parts.append(system_prompt)
    return "\n\n".join(parts)


async def ask(
    text: str,
    system_prompt: str | None = None,
    user: dict[str, Any] | None = None,
    device: dict[str, Any] | None = None,
    allowed_widget_ids: list[str] | None = None,
) -> str:
    # MCP servers (if any are configured) are connected fresh for each call
    # and torn down afterwards — tools from local plugins and MCP servers are
    # merged into one bridge, so the model can't tell (or needs to care)
    # where a given tool came from.
    async with MCPToolSource(load_mcp_server_configs()) as mcp_source:
        plugins = registry.all()
        if allowed_widget_ids is not None:
            plugins = [plugin for plugin in plugins if plugin.id in allowed_widget_ids]
        # user/device are only available for the interactive voice/text route
        # (POST /api/assistant/ask) — the scheduled AI-insights job has no
        # request context, so it keeps reading each plugin's base/shared
        # settings, same as before. When present, resolve each plugin's
        # personal/device-scoped settings the same way the dashboard tile
        # does, so voice sees the same data the user configured (e.g. which
        # calendars to show), not the registry singleton's base config.
        if user is not None and device is not None:
            plugins = [await scoped_plugin(plugin, user, device) for plugin in plugins]

        settings = effective_settings()
        searxng_url = settings.get("searxng_url")
        web_tools = get_web_tools(searxng_url) if (allowed_widget_ids is None and searxng_url) else []

        tools = [tool for plugin in plugins for tool in plugin.get_ai_tools()] + await mcp_source.tools() + web_tools
        provider = AIProvider(ToolBridge(tools))
        full_system_prompt = _build_system_prompt(system_prompt)
        return await provider.run_prompt(text, system_prompt=full_system_prompt)
