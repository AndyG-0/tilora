from __future__ import annotations

from typing import Any

import pytest

from app.plugins.base import Plugin, PluginRegistry, ToolDef


class FakePlugin(Plugin):
    id = "fake"
    name = "Fake"

    async def get_summary(self) -> dict[str, Any]:
        return {"ok": True}

    async def get_detail(self) -> dict[str, Any]:
        return {"ok": True, "detail": True}

    def get_ai_tools(self) -> list[ToolDef]:
        async def handler() -> str:
            return "called"

        return [ToolDef(name="fake_tool", description="d", parameters={}, handler=handler)]


class ToollessPlugin(Plugin):
    id = "toolless"
    name = "Toolless"

    async def get_summary(self) -> dict[str, Any]:
        return {}

    async def get_detail(self) -> dict[str, Any]:
        return {}


def test_register_and_get():
    registry = PluginRegistry()
    plugin = FakePlugin({})
    registry.register(plugin)
    assert registry.get("fake") is plugin


def test_get_unknown_returns_none():
    registry = PluginRegistry()
    assert registry.get("missing") is None


def test_register_duplicate_id_raises():
    registry = PluginRegistry()
    registry.register(FakePlugin({}))
    with pytest.raises(ValueError):
        registry.register(FakePlugin({}))


def test_all_returns_every_registered_plugin():
    registry = PluginRegistry()
    a, b = FakePlugin({}), ToollessPlugin({})
    registry.register(a)
    registry.register(b)
    assert set(registry.all()) == {a, b}


def test_all_tools_aggregates_across_plugins():
    registry = PluginRegistry()
    registry.register(FakePlugin({}))
    registry.register(ToollessPlugin({}))
    tools = registry.all_tools()
    assert [t.name for t in tools] == ["fake_tool"]
