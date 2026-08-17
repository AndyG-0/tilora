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
from typing import Any, ClassVar, Literal


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
    #: True marks this as a "navigate to my own detail page" tool rather than
    #: an ordinary data tool -- its successful result is captured by
    #: ToolBridge as the frontend navigation action, in addition to being fed
    #: back to the model like any other tool result. See ToolBridge.call.
    is_navigation: bool = False


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
    #: who this widget's settings belong to. "network" (the default) means
    #: one shared config for the whole household (e.g. a NAS or router — same
    #: for everyone), viewable by any logged-in user but writable only by an
    #: admin. "personal" means each household member has their own settings
    #: *and* sees their own content on the tile (e.g. RSS feeds, calendar
    #: selection) — see app.api.widgets for how this is enforced/personalized.
    settings_scope: ClassVar[Literal["network", "personal"]] = "network"
    #: settings keys any logged-in user may override for the specific device
    #: they're currently on, layered on top of whatever settings_scope above
    #: already resolved to (network default, or personal). Orthogonal to
    #: settings_scope, not a replacement for it — e.g. a "network"-scope
    #: plugin's shared connection info (host/credentials) still needs an
    #: admin to change, but a field like Jellyfin's playback_mode depends on
    #: *this device's* hardware/browser, not who's logged in or household
    #: policy, so any user may tune it for their own device without needing
    #: admin rights — see app.api.widgets for resolution/persistence.
    device_overridable_settings: ClassVar[frozenset[str]] = frozenset()
    #: if set, this plugin's connection settings (host/port/credentials) live
    #: in a shared `network_integrations` DB row of this type rather than in
    #: dashboard.yaml/widget_settings — see app.plugins.network_settings.
    #: None (the default) means this plugin is unrelated to that mechanism.
    #: Orthogonal to settings_scope above: that axis is personal-vs-household,
    #: this one is per-widget-instance-vs-shared-physical-device.
    network_integration_type: ClassVar[str | None] = None
    #: only meaningful when network_integration_type is set. True (the
    #: default): exactly one network_integrations row of this type exists,
    #: looked up directly by type. False: a widget instance must say *which*
    #: row via its own `network_integration_id` setting, since more than one
    #: named connection of this type can exist — only ContainerPlugin sets
    #: this, since dashboard.yaml already configures two Container widgets
    #: (Docker, Podman) pointing at two different hosts.
    network_integration_singleton: ClassVar[bool] = True
    #: starter values for this type's network_integrations row — the
    #: connection-field subset that used to live in default_settings before
    #: this plugin opted into network_integration_type.
    network_default_settings: ClassVar[dict[str, Any]] = {}

    def __init__(self, config: dict[str, Any]):
        self.config = config
        # dashboard.yaml widget ids conventionally match the class default
        # (e.g. "weather"), but a UI-added widget gets a generated id so two
        # widgets of the same type can coexist — the instance's config wins.
        self.id = config.get("id", self.id)
        # BCP-47-ish locale code (e.g. "en", "es") a plugin may use via
        # app.i18n.t() to translate any server-synthesized text (condition
        # labels, error messages) — see with_settings/scoped_plugin for how
        # this is resolved per request without mutating the registry
        # singleton. Most plugin output is data the frontend formats itself,
        # so most plugins never read this.
        self.locale: str = config.get("locale", "en")
        # id of the household member this instance was cloned for, set by
        # scoped_plugin() for "personal"-scope plugins whose content is
        # per-user rather than just per-user-*settings* (e.g. a chore list
        # keyed by owner, not just a differently-configured shared feed).
        # None on the registry singleton and for "network"-scope plugins,
        # where there's no single owning user. Named requesting_user_id
        # rather than user_id to avoid colliding with plugins (e.g.
        # Goodreads) that already have their own settings-derived user_id
        # property for an unrelated external account id.
        self.requesting_user_id: str | None = config.get("user_id")

    @abstractmethod
    async def get_summary(self) -> dict[str, Any]:
        """Data for the widget's dashboard-grid tile."""

    @abstractmethod
    async def get_detail(self) -> dict[str, Any]:
        """Data for the widget's tap-to-drill-down detail view."""

    def get_ai_tools(self) -> list[ToolDef]:
        """Tools this plugin exposes to the AI layer. Optional to override."""
        return []

    def validate_settings(self, payload: dict[str, Any]) -> None:
        """Reject a settings patch before it's persisted, by raising ValueError.

        `PATCH /api/widgets/{id}/settings` already restricts *which* keys can
        be set (to those in `default_settings`), but says nothing about their
        values, so a typo in a field the backend later looks up in a table
        silently degrades to that table's default with no error anywhere.
        Override to check the values that have a fixed set of valid ones;
        the route turns the ValueError into a 400. Optional to override.
        """
        return None

    def with_settings(
        self, settings: dict[str, Any] | None = None, locale: str | None = None, user_id: str | None = None
    ) -> Plugin:
        """A fresh instance of this plugin carrying different settings/locale/user.

        Used to personalize a "personal"-scope plugin (or a plugin whose
        requester's locale differs from this instance's) per request without
        mutating the shared registry singleton — get_summary/get_detail are
        async with awaited I/O, so two users' requests interleaving on the
        event loop could otherwise corrupt each other's view if the
        singleton's settings/locale were mutated in place instead. Requires
        __init__ to stay cheap/side-effect-free, which holds for every plugin
        today.
        """
        return type(self)(
            {
                **self.config,
                "settings": settings if settings is not None else self.config["settings"],
                "locale": locale or self.locale,
                "user_id": user_id if user_id is not None else self.requesting_user_id,
            }
        )


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
