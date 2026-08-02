"""Plugin interface and registry.

Every integration (weather, photos, movies, AI-driven widgets, ...) is a
`Plugin` subclass. Plugins are self-contained: they know how to produce
summary/detail data for their widget and, optionally, expose tools the AI
layer can call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True)
class ToolDef:
    """A callable capability a plugin exposes to the AI layer.

    `parameters` is a JSON Schema object describing the tool's arguments,
    matching the shape every major LLM tool-calling API expects. Keeping it
    as a plain dict (rather than a litellm-specific type) is what lets this
    same definition be served by a real MCP server later without changing
    the plugins that define tools.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


class Plugin(ABC):
    """Base class every dashboard plugin must implement."""

    #: unique, stable identifier used in URLs and config (e.g. "weather")
    id: str
    #: human-readable name shown in the UI
    name: str
    #: how often the dashboard should poll this widget's summary, in seconds
    refresh_interval_seconds: int = 300
    #: starter settings for a widget of this type added via the UI, which
    #: has no dashboard.yaml entry to inherit settings from
    default_settings: ClassVar[dict[str, Any]] = {}
    #: starter grid footprint for a widget of this type added via the UI —
    #: most widgets are fine at a single cell, but content-heavy ones (e.g.
    #: a list of RSS headlines) need more room to be readable by default
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 1}

    def __init__(self, config: dict[str, Any]):
        self.config = config
        # dashboard.yaml widget ids conventionally match the class default
        # (e.g. "weather"), but a UI-added widget gets a generated id so two
        # widgets of the same type can coexist — the instance's config wins.
        self.id = config.get("id", self.id)

    @abstractmethod
    async def get_summary(self) -> dict[str, Any]:
        """Data for the widget's dashboard-grid tile."""

    @abstractmethod
    async def get_detail(self) -> dict[str, Any]:
        """Data for the widget's tap-to-drill-down detail view."""

    def get_ai_tools(self) -> list[ToolDef]:
        """Tools this plugin exposes to the AI layer. Optional to override."""
        return []


class PluginRegistry:
    """Holds constructed plugin instances, keyed by plugin id."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        if plugin.id in self._plugins:
            raise ValueError(f"Plugin id '{plugin.id}' is already registered")
        self._plugins[plugin.id] = plugin

    def get(self, plugin_id: str) -> Plugin | None:
        return self._plugins.get(plugin_id)

    def unregister(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)

    def all(self) -> list[Plugin]:
        return list(self._plugins.values())

    def all_tools(self) -> list[ToolDef]:
        tools: list[ToolDef] = []
        for plugin in self._plugins.values():
            tools.extend(plugin.get_ai_tools())
        return tools


registry = PluginRegistry()
