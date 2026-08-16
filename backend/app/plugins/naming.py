"""Human-meaningful display names for widget instances.

Multiple instances of the same tile type can coexist (two Weather tiles,
two Container tiles for Docker/Podman, ...). Nothing about `Plugin.name`
(a class-level type name, e.g. "Weather") distinguishes them, which shows
up anywhere instances are listed for the user to pick from (AI insights
topics, the screensaver widget picker). `display_names` is the one place
that computes a name for each instance so every such list agrees.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.plugins.base import Plugin
from app.storage.db import get_network_integration, list_widget_custom_names


def _raw_label(plugin: Plugin) -> str:
    settings = plugin.config.get("settings", {}) if hasattr(plugin, "config") else {}

    location = settings.get("location_name")
    if location:
        return f"{plugin.name} ({location})"

    if plugin.network_integration_type:
        integration_id = settings.get("network_integration_id")
        integration = get_network_integration(integration_id) if integration_id else None
        if integration:
            return f"{plugin.name} ({integration['name']})"

    title = settings.get("title")
    if title and title != plugin.name:
        return f"{plugin.name} ({title})"

    return plugin.name


def display_names(plugins: Iterable[Plugin]) -> dict[str, str]:
    """widget_id -> unique, human-meaningful display name for every plugin passed in.

    Priority: an explicit user-set override (`widget_custom_names`) wins
    outright. Otherwise a label is derived from a distinguishing setting
    (location_name, network integration name, or a custom title). If two or
    more instances of the same type still land on the same label, a stable
    " (2)", " (3)", ... suffix is appended, ordered by widget id (not list
    order, which callers may reshuffle between requests) so a given
    instance's label doesn't change from render to render.
    """
    plugins = list(plugins)
    overrides = list_widget_custom_names()

    raw: dict[str, str] = {}
    for plugin in plugins:
        override = overrides.get(plugin.id)
        raw[plugin.id] = override if override else _raw_label(plugin)

    groups: dict[tuple[str, str], list[str]] = {}
    for plugin in plugins:
        if plugin.id in overrides:
            continue
        key = (type(plugin).__name__, raw[plugin.id])
        groups.setdefault(key, []).append(plugin.id)

    names = dict(raw)
    for widget_ids in groups.values():
        if len(widget_ids) < 2:
            continue
        for index, widget_id in enumerate(sorted(widget_ids), start=1):
            if index > 1:
                names[widget_id] = f"{raw[widget_id]} ({index})"

    return names
