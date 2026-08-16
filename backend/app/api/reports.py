from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from app.auth import get_current_device, get_current_user
from app.config import list_widget_configs, load_dashboard_config, resolve_tabs
from app.plugins.base import registry
from app.plugins.naming import _raw_label, display_names
from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE
from app.storage.db import (
    get_tile_report_stats,
    hidden_widget_ids,
    list_custom_widgets,
    list_devices,
    list_network_integrations,
    list_users,
    list_widget_custom_names,
    list_widget_layouts,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _describe_size(col_span: int, row_span: int) -> str:
    known = {
        (1, 1): "Compact (1 × 1)",
        (2, 1): "Wide (2 × 1)",
        (2, 2): "Standard (2 × 2)",
        (2, 3): "Tall (2 × 3)",
        (4, 1): "Banner (4 × 1)",
        (4, 2): "Large (4 × 2)",
        (4, 3): "Extra Large (4 × 3)",
        (4, 4): "Full Grid (4 × 4)",
    }
    return known.get((col_span, row_span), f"{col_span} × {row_span}")


def _build_tiles_report_sync(user_id: str, device_id: str) -> dict[str, Any]:
    config = load_dashboard_config()
    tabs = resolve_tabs(config)
    tab_names = {t["id"]: t["name"] for t in tabs}
    default_tab_id = tabs[0]["id"] if tabs else "home"
    default_tab_name = tabs[0]["name"] if tabs else "Home"

    all_widget_configs = list_widget_configs(config)
    custom_widget_map = {w["id"]: w for w in list_custom_widgets()}
    custom_names = list_widget_custom_names()
    hidden_ids = hidden_widget_ids(user_id, device_id)
    users_map = {u["id"]: u["name"] for u in list_users()}
    devices_map = {d["id"]: d["name"] for d in list_devices()}
    wide_layouts = list_widget_layouts(user_id, device_id, "wide")
    db_stats = get_tile_report_stats()
    network_integrations_map = {i["id"]: i for i in list_network_integrations()}

    # Plugins for display_names
    registered_plugins = [registry.get(w["id"]) for w in all_widget_configs]
    live_plugins = [p for p in registered_plugins if p is not None]
    computed_display_names = display_names(live_plugins)

    tiles: list[dict[str, Any]] = []

    for w in all_widget_configs:
        widget_id = w["id"]
        widget_type = w.get("type", "unknown")
        plugin_cls = PLUGIN_CLASSES_BY_TYPE.get(widget_type)
        type_name = plugin_cls.name if plugin_cls else widget_type.title()

        is_custom = widget_id in custom_widget_map
        source = "custom" if is_custom else "builtin"

        custom_widget_row = custom_widget_map.get(widget_id, {})
        owner_user_id = custom_widget_row.get("owner_user_id") or w.get("owner_user_id")
        owner_device_id = custom_widget_row.get("owner_device_id") or w.get("owner_device_id")

        owner_user_name = users_map.get(owner_user_id, owner_user_id) if owner_user_id else "System / Shared"
        owner_device_name = devices_map.get(owner_device_id, owner_device_id) if owner_device_id else "All Devices"

        custom_name = custom_names.get(widget_id, "")
        has_custom_name = bool(custom_name)

        plugin = registry.get(widget_id)
        default_name = _raw_label(plugin) if plugin else type_name
        name = computed_display_names.get(widget_id, custom_name or default_name)

        tab_id = w.get("tab") or default_tab_id
        tab_name = tab_names.get(tab_id, default_tab_name)

        # Base layout from config merged with wide layout override
        base_layout = w.get("layout", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
        effective_layout = {**base_layout, **wide_layouts.get(widget_id, {})}
        col_span = effective_layout.get("colSpan", 1)
        row_span = effective_layout.get("rowSpan", 1)
        size_description = _describe_size(col_span, row_span)

        if plugin is not None:
            scope = str(plugin.settings_scope)
        elif plugin_cls is not None:
            scope_attr = getattr(plugin_cls, "settings_scope", "network")
            if isinstance(scope_attr, property):
                scope = str(plugin_cls({"id": "", "settings": dict(plugin_cls.default_settings)}).settings_scope)
            else:
                scope = str(scope_attr)
        else:
            scope = "network"

        device_overridable = bool(plugin_cls.device_overridable_settings) if plugin_cls else False
        refresh_interval = plugin.refresh_interval_seconds if plugin else 300

        # Network integration if applicable
        network_integration_name = None
        if plugin_cls and plugin_cls.network_integration_type:
            settings = plugin.config.get("settings", {}) if plugin and hasattr(plugin, "config") else {}
            integration_id = settings.get("network_integration_id")
            if integration_id:
                integration = network_integrations_map.get(integration_id)
                if integration:
                    network_integration_name = integration.get("name")
            elif plugin_cls.network_integration_singleton:
                integration = network_integrations_map.get(plugin_cls.network_integration_type)
                if integration:
                    network_integration_name = integration.get("name")

        stat = db_stats.get(
            widget_id,
            {
                "chores_active": 0,
                "chores_total": 0,
                "shopping_active": 0,
                "shopping_total": 0,
                "alerts_active": 0,
                "photos_count": 0,
                "packages_count": 0,
                "has_custom_settings": False,
                "has_user_settings": False,
                "has_device_settings": False,
                "has_layout_overrides": False,
            },
        )

        is_hidden = widget_id in hidden_ids

        tiles.append(
            {
                "id": widget_id,
                "type": widget_type,
                "type_name": type_name,
                "name": name,
                "custom_name": custom_name or None,
                "default_name": default_name,
                "has_custom_name": has_custom_name,
                "source": source,
                "tab_id": tab_id,
                "tab_name": tab_name,
                "layout": effective_layout,
                "size_description": size_description,
                "owner_user_id": owner_user_id,
                "owner_user_name": owner_user_name,
                "owner_device_id": owner_device_id,
                "owner_device_name": owner_device_name,
                "settings_scope": scope,
                "device_overridable": device_overridable,
                "refresh_interval_seconds": refresh_interval,
                "network_integration": network_integration_name,
                "is_hidden": is_hidden,
                "stats": stat,
            }
        )

    total_tiles = len(tiles)
    custom_tiles = sum(1 for t in tiles if t["source"] == "custom")
    builtin_tiles = sum(1 for t in tiles if t["source"] == "builtin")
    custom_named_tiles = sum(1 for t in tiles if t["has_custom_name"])
    hidden_tiles = sum(1 for t in tiles if t["is_hidden"])

    return {
        "summary": {
            "total_tiles": total_tiles,
            "custom_tiles": custom_tiles,
            "builtin_tiles": builtin_tiles,
            "custom_named_tiles": custom_named_tiles,
            "hidden_tiles": hidden_tiles,
            "tabs_count": len(tabs),
        },
        "tiles": tiles,
    }


@router.get("/tiles")
async def get_tiles_report(
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    return await asyncio.to_thread(_build_tiles_report_sync, user["id"], device["id"])
