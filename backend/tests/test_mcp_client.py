from __future__ import annotations

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from app import config
from app.ai.mcp_client import MCPServerConfig, MCPToolSource, _tool_def, load_mcp_server_configs


def make_add_server() -> FastMCP:
    server = FastMCP("test-server")

    @server.tool()
    async def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    return server


async def test_tool_def_exposes_mcp_tool_schema():
    server = make_add_server()
    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()
        tool_def = _tool_def(session, listed.tools[0])

        assert tool_def.name == "add"
        assert tool_def.description == "Add two numbers."
        assert tool_def.parameters["properties"].keys() == {"a", "b"}


async def test_tool_def_handler_dispatches_call_and_unwraps_text_content():
    server = make_add_server()
    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()
        tool_def = _tool_def(session, listed.tools[0])

        result = await tool_def.handler(a=2, b=3)

        assert result == "5"


async def test_mcp_tool_source_with_no_servers_yields_no_tools():
    async with MCPToolSource([]) as source:
        assert await source.tools() == []


async def test_mcp_tool_source_rejects_server_without_command_or_url():
    server_config = MCPServerConfig(name="broken")

    with pytest.raises(ValueError, match="broken"):
        async with MCPToolSource([server_config]):
            pass


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
  - name: remote
    url: "https://example.com/mcp"

widgets: []
"""
    )
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)
    return path


def test_load_mcp_server_configs_parses_stdio_and_url_servers(dashboard_yaml):
    servers = load_mcp_server_configs()

    assert servers == [
        MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            env=None,
            url=None,
        ),
        MCPServerConfig(name="remote", command=None, args=[], env=None, url="https://example.com/mcp"),
    ]


def test_load_mcp_server_configs_defaults_to_empty_list(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text("widgets: []\n")
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)

    assert load_mcp_server_configs() == []
