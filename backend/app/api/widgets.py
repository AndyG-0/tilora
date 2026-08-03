from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_device, get_current_user
from app.config import list_widget_configs, load_dashboard_config, resolve_tabs
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import Plugin, registry
from app.plugins.photos.plugin import PhotosPlugin
from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE
from app.scheduler import run_ai_widget, schedule_ai_widget, schedule_photo_index, unschedule_widget
from app.storage.cache import cache
from app.storage.db import (
    delete_custom_widget,
    delete_photo_index,
    delete_widget_device_settings,
    delete_widget_device_settings_for_widget,
    delete_widget_layout_for_widget,
    delete_widget_user_settings_for_widget,
    get_widget_device_settings,
    get_widget_user_settings,
    list_custom_widgets,
    list_widget_layouts,
    mark_widget_removed,
    save_custom_widget,
    save_widget_device_settings,
    save_widget_layout,
    save_widget_settings,
    save_widget_user_settings,
)

# Settings keys whose change should trigger an immediate photo re-index —
# these affect what the source enumerates, unlike e.g. `interval_seconds`
# (slideshow cadence) or `index_refresh_seconds` itself.
_PHOTO_INDEX_RELEVANT_SETTINGS = {
    "provider",
    "directory",
    "recursive",
    "album_token",
    "album_name",
    "base_url",
    "api_key",
    "album_id",
}


class WidgetLayout(BaseModel):
    col: int
    row: int
    colSpan: int
    rowSpan: int


class WidgetLayoutUpdate(BaseModel):
    id: str
    layout: WidgetLayout


class UpdateWidgetsLayoutRequest(BaseModel):
    widgets: list[WidgetLayoutUpdate]


class AddWidgetRequest(BaseModel):
    type: str
    layout: WidgetLayout
    tab: str | None = None


router = APIRouter(prefix="/api/widgets", tags=["widgets"])


def _list_widgets_sync(user_id: str, device_id: str) -> list[dict[str, Any]]:
    config = load_dashboard_config()
    default_tab = resolve_tabs(config)[0]["id"]
    layouts = list_widget_layouts(user_id, device_id)
    return [
        {
            "id": w["id"],
            "type": w["type"],
            # A drag-to-rearrange edit persisted at runtime overrides the
            # dashboard.yaml position, scoped to this (user, device) pair —
            # the same layering pattern widget settings overrides use, just
            # with an extra dimension.
            "layout": {**w["layout"], **layouts.get(w["id"], {})},
            "tab": w.get("tab", default_tab),
        }
        for w in list_widget_configs(config)
        if w.get("enabled", True)
    ]


@router.get("")
async def list_widgets(
    user: dict[str, Any] = Depends(get_current_user), device: dict[str, Any] = Depends(get_current_device)
):
    # One thread hop for the whole list (config-file read + one bulk layout
    # query) rather than one per widget — cheaper than to_thread-per-call
    # and this whole read is what needs to move off the event loop, not each
    # individual piece of it.
    return await asyncio.to_thread(_list_widgets_sync, user["id"], device["id"])


@router.get("/types")
async def widget_types():
    return [
        {"type": type_, "name": plugin_cls.name, "default_layout": plugin_cls.default_layout}
        for type_, plugin_cls in PLUGIN_CLASSES_BY_TYPE.items()
    ]


@router.put("/layout")
async def update_widgets_layout(
    payload: UpdateWidgetsLayoutRequest,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    for entry in payload.widgets:
        await asyncio.to_thread(save_widget_layout, user["id"], device["id"], entry.id, entry.layout.model_dump())
    return {"status": "ok"}


@router.post("")
async def add_widget(payload: AddWidgetRequest):
    plugin_cls = PLUGIN_CLASSES_BY_TYPE.get(payload.type)
    if plugin_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown widget type '{payload.type}'")

    widget_id = f"{payload.type}-{uuid4().hex[:8]}"
    while registry.get(widget_id) is not None:
        widget_id = f"{payload.type}-{uuid4().hex[:8]}"

    layout = payload.layout.model_dump()
    tab = payload.tab
    settings = dict(plugin_cls.default_settings)

    await asyncio.to_thread(save_custom_widget, widget_id, payload.type, layout, tab)
    # A UI-added widget has no dashboard.yaml entry to source settings from —
    # persist the plugin's starter settings the same way a runtime settings
    # edit would, so they survive a backend restart.
    if settings:
        await asyncio.to_thread(save_widget_settings, widget_id, settings)

    plugin = plugin_cls({"id": widget_id, "settings": settings})
    registry.register(plugin)
    if isinstance(plugin, AIInsightsPlugin):
        schedule_ai_widget(plugin)
    elif isinstance(plugin, PhotosPlugin):
        schedule_photo_index(plugin)

    default_tab = resolve_tabs(load_dashboard_config())[0]["id"]
    return {"id": widget_id, "type": payload.type, "layout": layout, "tab": tab or default_tab}


def _get_plugin(widget_id: str):
    plugin = registry.get(widget_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Unknown widget '{widget_id}'")
    return plugin


def _require_write_access(plugin: Plugin, user: dict[str, Any]) -> None:
    # "network"-scope settings (NAS/router/media-server credentials, ...) are
    # shared by the whole household — only an admin may change them. Any
    # logged-in user may still read them (enforced by the login dependency on
    # the GET routes below). "personal"-scope settings are each user's own,
    # so no extra check is needed beyond being logged in as that user.
    if plugin.settings_scope == "network" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


async def _scoped_plugin(plugin: Plugin, user: dict[str, Any], device: dict[str, Any]) -> Plugin:
    """The plugin instance to read from for this request.

    "network"-scope plugins render the same content for everyone, so the
    registry singleton is used directly, unless the plugin also opts specific
    keys into device_overridable_settings (see below). "personal"-scope
    plugins get a throwaway instance carrying this user's own settings
    layered on top of the widget's baseline — see Plugin.with_settings.

    Device overrides layer on top of whichever of the above the settings
    dict already reflects — network default or personal override — so an
    unset device just inherits it, no separate fallback logic needed.
    """
    settings = None
    if plugin.settings_scope == "personal":
        overrides = await asyncio.to_thread(get_widget_user_settings, user["id"], plugin.id) or {}
        settings = {**plugin.config["settings"], **overrides}
    if plugin.device_overridable_settings:
        device_overrides = await asyncio.to_thread(get_widget_device_settings, device["id"], plugin.id) or {}
        settings = {
            **(settings if settings is not None else plugin.config["settings"]),
            **{k: v for k, v in device_overrides.items() if k in plugin.device_overridable_settings},
        }
    if settings is None:
        return plugin
    return plugin.with_settings(settings)


def _cache_key(kind: str, plugin: Plugin, user: dict[str, Any], device: dict[str, Any]) -> str:
    parts = [kind, plugin.id]
    if plugin.settings_scope == "personal":
        parts.append(user["id"])
    if plugin.device_overridable_settings:
        parts.append(device["id"])
    return ":".join(parts)


@router.get("/{widget_id}/summary")
async def widget_summary(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    cache_key = _cache_key("summary", plugin, user, device)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    scoped = await _scoped_plugin(plugin, user, device)
    data = await scoped.get_summary()
    cache.set(cache_key, data, plugin.refresh_interval_seconds)
    return data


@router.get("/{widget_id}/detail")
async def widget_detail(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    cache_key = _cache_key("detail", plugin, user, device)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    scoped = await _scoped_plugin(plugin, user, device)
    data = await scoped.get_detail()
    cache.set(cache_key, data, plugin.refresh_interval_seconds)
    return data


@router.patch("/{widget_id}/settings")
async def update_widget_settings(
    widget_id: str,
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)

    if plugin.settings_scope == "personal":
        current = await asyncio.to_thread(get_widget_user_settings, user["id"], widget_id) or {}
        merged = {**plugin.config["settings"], **current, **payload}
        await asyncio.to_thread(save_widget_user_settings, user["id"], widget_id, merged)
        if plugin.device_overridable_settings:
            cache.delete_prefix(f"summary:{widget_id}:{user['id']}:")
            cache.delete_prefix(f"detail:{widget_id}:{user['id']}:")
        else:
            cache.delete(_cache_key("summary", plugin, user, device))
            cache.delete(_cache_key("detail", plugin, user, device))
        return merged

    _require_write_access(plugin, user)
    plugin.config["settings"].update(payload)
    await asyncio.to_thread(save_widget_settings, widget_id, plugin.config["settings"])
    # Force the next summary/detail request to reflect the new settings
    # instead of serving a stale cached response. A plugin with
    # device_overridable_settings fans its cache entries out by device
    # (_cache_key appends device["id"]), so the plain widget-level key alone
    # won't catch them — sweep every "{kind}:{widget_id}:*" entry too.
    cache.delete(f"summary:{widget_id}")
    cache.delete(f"detail:{widget_id}")
    if plugin.device_overridable_settings:
        cache.delete_prefix(f"summary:{widget_id}:")
        cache.delete_prefix(f"detail:{widget_id}:")
    if isinstance(plugin, PhotosPlugin) and _PHOTO_INDEX_RELEVANT_SETTINGS & payload.keys():
        schedule_photo_index(plugin)
    return plugin.config["settings"]


@router.get("/{widget_id}/device-settings")
async def get_widget_device_settings_route(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    # Unused `user` param keeps this route behind login like every other
    # widget route, even though the value itself isn't needed — the override
    # is keyed by device, not user.
    del user
    _get_plugin(widget_id)
    return await asyncio.to_thread(get_widget_device_settings, device["id"], widget_id) or {}


@router.patch("/{widget_id}/device-settings")
async def update_widget_device_settings_route(
    widget_id: str,
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    unknown = payload.keys() - plugin.device_overridable_settings
    if unknown:
        raise HTTPException(status_code=400, detail=f"Not device-overridable: {', '.join(sorted(unknown))}")

    current = await asyncio.to_thread(get_widget_device_settings, device["id"], widget_id) or {}
    merged = {**current, **payload}
    await asyncio.to_thread(save_widget_device_settings, device["id"], widget_id, merged)
    cache.delete(_cache_key("summary", plugin, user, device))
    cache.delete(_cache_key("detail", plugin, user, device))
    return merged


@router.delete("/{widget_id}/device-settings")
async def clear_widget_device_settings_route(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    await asyncio.to_thread(delete_widget_device_settings, device["id"], widget_id)
    cache.delete(_cache_key("summary", plugin, user, device))
    cache.delete(_cache_key("detail", plugin, user, device))
    return {"status": "ok"}


@router.post("/{widget_id}/run")
async def run_widget_now(widget_id: str, user: dict[str, Any] = Depends(get_current_user)):
    plugin = _get_plugin(widget_id)
    if not isinstance(plugin, AIInsightsPlugin):
        raise HTTPException(status_code=400, detail=f"Widget '{widget_id}' cannot be run on demand")

    await run_ai_widget(plugin)
    cache.delete(f"summary:{widget_id}")
    cache.delete(f"detail:{widget_id}")

    data = await plugin.get_detail()
    cache.set(f"detail:{widget_id}", data, plugin.refresh_interval_seconds)
    return data


@router.delete("/{widget_id}")
async def remove_widget(widget_id: str):
    plugin = _get_plugin(widget_id)

    custom_widgets = await asyncio.to_thread(list_custom_widgets)
    custom_ids = {w["id"] for w in custom_widgets}
    if widget_id in custom_ids:
        await asyncio.to_thread(delete_custom_widget, widget_id)
    else:
        # A dashboard.yaml-defined widget can't be deleted from the file —
        # only hidden, the same layering pattern as settings/layout overrides.
        await asyncio.to_thread(mark_widget_removed, widget_id)
    await asyncio.to_thread(delete_widget_layout_for_widget, widget_id)
    await asyncio.to_thread(delete_widget_user_settings_for_widget, widget_id)
    await asyncio.to_thread(delete_widget_device_settings_for_widget, widget_id)

    registry.unregister(widget_id)
    unschedule_widget(widget_id)
    if isinstance(plugin, PhotosPlugin):
        await asyncio.to_thread(delete_photo_index, widget_id)
    cache.delete(f"summary:{widget_id}")
    cache.delete(f"detail:{widget_id}")
    if plugin.device_overridable_settings:
        cache.delete_prefix(f"summary:{widget_id}:")
        cache.delete_prefix(f"detail:{widget_id}:")
    return {"status": "ok"}
