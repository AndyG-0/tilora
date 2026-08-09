"""Resolves and propagates `network_integrations` connection settings —
shared, admin-edited config for a physical LAN device (Pi-hole, Jellyfin,
Synology, Asus Router, HDHomeRun, or a named Docker/Podman host) — into the
plugin instances that use them.

Distinct from `app.plugins.scoping`, which layers personal/device overrides
onto a plugin's *existing* settings dict per request. This module instead
supplies part of that dict in the first place: `Plugin.network_integration_type`
marks which plugins have connection fields living in a `network_integrations`
DB row rather than dashboard.yaml/widget_settings — see that ClassVar's
docstring in `app.plugins.base` for why this is a separate axis from
`settings_scope`.
"""

from __future__ import annotations

from typing import Any

from app.plugins.base import Plugin, registry
from app.storage.db import get_network_integration, save_network_integration


def resolve_network_settings(plugin_cls: type[Plugin], widget_settings: dict[str, Any]) -> dict[str, Any]:
    """The connection-field dict this plugin type/instance should use, or {}
    if unconfigured (no row yet, or — for a multi-instance type like
    Container — no `network_integration_id` picked yet)."""
    if not plugin_cls.network_integration_type:
        return {}
    if plugin_cls.network_integration_singleton:
        row = get_network_integration(plugin_cls.network_integration_type)
    else:
        integration_id = widget_settings.get("network_integration_id")
        row = get_network_integration(integration_id) if integration_id else None
    return row["settings"] if row else {}


def apply_network_integration_update(type_: str, integration_id: str, settings: dict[str, Any]) -> list[str]:
    """Mutates every currently-registered plugin instance of this
    type/specific instance in place with the new connection settings, so the
    change is live without a backend restart. Returns the affected widget
    ids so the caller can invalidate their summary/detail cache entries."""
    affected: list[str] = []
    for plugin in registry.all():
        plugin_cls = type(plugin)
        if plugin_cls.network_integration_type != type_:
            continue
        if not plugin_cls.network_integration_singleton:
            if plugin.config["settings"].get("network_integration_id") != integration_id:
                continue
        plugin.config["settings"].update(settings)
        affected.append(plugin.id)
    return affected


def ensure_network_integration_defaults() -> None:
    """Idempotent: creates a starter row for any singleton integration type
    that doesn't have one yet (a fresh install, or a new integration type
    added after this migration/mechanism shipped). Never overwrites an
    existing row — Container is skipped entirely since it has no single
    default row to seed (its rows are created explicitly, one per named
    host, via migration 007 or the network-settings API)."""
    from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE

    for plugin_cls in PLUGIN_CLASSES_BY_TYPE.values():
        type_ = plugin_cls.network_integration_type
        if not type_ or not plugin_cls.network_integration_singleton:
            continue
        if get_network_integration(type_) is None:
            save_network_integration(type_, type_, plugin_cls.name, dict(plugin_cls.network_default_settings))
