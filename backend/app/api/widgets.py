from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_device, get_current_user, require_write_access
from app.config import list_widget_configs, load_dashboard_config, resolve_tabs
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import Plugin, registry
from app.plugins.network_settings import resolve_network_settings
from app.plugins.photos.plugin import PhotosPlugin
from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE
from app.plugins.scoping import scoped_plugin
from app.plugins.speedtest.plugin import SpeedtestPlugin
from app.scheduler import (
    run_ai_widget,
    run_speedtest_widget,
    schedule_ai_widget,
    schedule_photo_index,
    schedule_speedtest_widget,
    unschedule_widget,
)
from app.storage.cache import cache
from app.storage.db import (
    delete_custom_widget,
    delete_photo_index,
    delete_widget_device_settings,
    delete_widget_device_settings_for_widget,
    delete_widget_layout_for_widget,
    delete_widget_user_settings_for_widget,
    get_user_preferences,
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


# Which viewport class a layout applies to, not which physical device — see
# the `widget_layout` table comment in app.storage.db.
Breakpoint = Literal["wide", "narrow"]


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
    breakpoint: Breakpoint


class AddWidgetRequest(BaseModel):
    type: str
    layout: WidgetLayout
    tab: str | None = None


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


def _list_widgets_sync(user_id: str, breakpoint: Breakpoint) -> list[dict[str, Any]]:
    config = load_dashboard_config()
    default_tab = resolve_tabs(config)[0]["id"]
    layouts = list_widget_layouts(user_id, breakpoint)
    return [
        {
            "id": w["id"],
            "type": w["type"],
            # A drag-to-rearrange edit persisted at runtime overrides the
            # dashboard.yaml position, scoped to this (user, breakpoint)
            # pair — the same layering pattern widget settings overrides
            # use, just with an extra dimension.
            "layout": {**w["layout"], **layouts.get(w["id"], {})},
            "tab": w.get("tab", default_tab),
        }
        for w in list_widget_configs(config)
        if w.get("enabled", True)
    ]


@router.get("")
async def list_widgets(breakpoint: Breakpoint, user: dict[str, Any] = Depends(get_current_user)):
    # One thread hop for the whole list (config-file read + one bulk layout
    # query) rather than one per widget — cheaper than to_thread-per-call
    # and this whole read is what needs to move off the event loop, not each
    # individual piece of it.
    return await asyncio.to_thread(_list_widgets_sync, user["id"], breakpoint)


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
):
    for entry in payload.widgets:
        await asyncio.to_thread(save_widget_layout, user["id"], payload.breakpoint, entry.id, entry.layout.model_dump())
    return {"status": "ok"}


@router.post("")
async def add_widget(payload: AddWidgetRequest, user: dict[str, Any] = Depends(get_current_user)):
    plugin_cls = PLUGIN_CLASSES_BY_TYPE.get(payload.type)
    if plugin_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown widget type '{payload.type}'")
    # No plugin instance exists yet to check via require_write_access, but
    # settings_scope is a ClassVar, so the class attribute is enough to
    # decide whether adding this widget type is an admin-only action.
    if plugin_cls.settings_scope == "network" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

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

    live_settings = settings
    if plugin_cls.network_integration_type:
        live_settings = {**settings, **resolve_network_settings(plugin_cls, settings)}
    plugin = plugin_cls({"id": widget_id, "settings": live_settings})
    registry.register(plugin)
    if isinstance(plugin, AIInsightsPlugin):
        schedule_ai_widget(plugin)
    elif isinstance(plugin, PhotosPlugin):
        schedule_photo_index(plugin)
    elif isinstance(plugin, SpeedtestPlugin):
        schedule_speedtest_widget(plugin)

    default_tab = resolve_tabs(load_dashboard_config())[0]["id"]
    return {"id": widget_id, "type": payload.type, "layout": layout, "tab": tab or default_tab}


def _get_plugin(widget_id: str):
    plugin = registry.get(widget_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Unknown widget '{widget_id}'")
    return plugin


def _cache_key_prefix(kind: str, plugin: Plugin, user: dict[str, Any], device: dict[str, Any]) -> str:
    parts = [kind, plugin.id]
    if plugin.settings_scope == "personal":
        parts.append(user["id"])
    if plugin.device_overridable_settings:
        parts.append(device["id"])
    return ":".join(parts) + ":"


async def _timed_call(kind: str, plugin: Plugin, call: Any) -> Any:
    """Await a plugin's get_summary()/get_detail() call, logging its latency
    and — separately — any exception it raises, tagged with the widget id
    and plugin class so slow/failing plugins are identifiable in logs
    without needing per-plugin instrumentation.
    """
    plugin_label = f"{plugin.id} ({type(plugin).__name__})"
    start = time.monotonic()
    try:
        result = await call
    except Exception:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception("widget %s %s failed after %.1fms", plugin_label, kind, elapsed_ms)
        raise
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info("widget %s %s took %.1fms", plugin_label, kind, elapsed_ms)
    return result


def _cache_key(kind: str, plugin: Plugin, user: dict[str, Any], device: dict[str, Any], locale: str) -> str:
    # locale is always the final segment — plugin output can be
    # locale-dependent (see app.i18n), so caching one locale's response and
    # serving it to a request for another locale would be a correctness bug,
    # not just cosmetic. Keeping it last (rather than interleaved with
    # user/device) means every prefix-based invalidation below still sweeps
    # every locale variant for a widget without needing locale-aware changes.
    return _cache_key_prefix(kind, plugin, user, device) + locale


@router.get("/{widget_id}/summary")
async def widget_summary(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    locale = (await asyncio.to_thread(get_user_preferences, user["id"])).get("locale", "en")
    cache_key = _cache_key("summary", plugin, user, device, locale)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    scoped = await scoped_plugin(plugin, user, device, locale)
    data = await _timed_call("summary", plugin, scoped.get_summary())
    cache.set(cache_key, data, plugin.refresh_interval_seconds)
    return data


@router.get("/{widget_id}/detail")
async def widget_detail(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    locale = (await asyncio.to_thread(get_user_preferences, user["id"])).get("locale", "en")
    cache_key = _cache_key("detail", plugin, user, device, locale)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    scoped = await scoped_plugin(plugin, user, device, locale)
    data = await _timed_call("detail", plugin, scoped.get_detail())
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

    try:
        plugin.validate_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if plugin.settings_scope == "personal":
        current = await asyncio.to_thread(get_widget_user_settings, user["id"], widget_id) or {}
        merged = {**plugin.config["settings"], **current, **payload}
        await asyncio.to_thread(save_widget_user_settings, user["id"], widget_id, merged)
        if plugin.device_overridable_settings:
            cache.delete_prefix(f"summary:{widget_id}:{user['id']}:")
            cache.delete_prefix(f"detail:{widget_id}:{user['id']}:")
        else:
            cache.delete_prefix(_cache_key_prefix("summary", plugin, user, device))
            cache.delete_prefix(_cache_key_prefix("detail", plugin, user, device))
        return merged

    require_write_access(plugin, user)
    plugin_cls = type(plugin)
    if plugin_cls.network_integration_type:
        # Connection fields (host, password, ...) live in a network
        # integration row now, edited only via /api/network-settings — this
        # route only accepts the plugin's remaining display-only keys (plus,
        # for Container, network_integration_id).
        allowed_keys = set(plugin_cls.default_settings.keys())
        invalid_keys = set(payload.keys()) - allowed_keys
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Connection settings for this widget type are edited at the network level "
                    f"(see /api/network-settings), not per-widget: {', '.join(sorted(invalid_keys))}"
                ),
            )
        plugin.config["settings"].update(payload)
        if not plugin_cls.network_integration_singleton:
            # e.g. Container: picking a different network_integration_id
            # means re-resolving which host's connection fields apply.
            plugin.config["settings"].update(resolve_network_settings(plugin_cls, plugin.config["settings"]))
        persisted = {k: v for k, v in plugin.config["settings"].items() if k in allowed_keys}
        await asyncio.to_thread(save_widget_settings, widget_id, persisted)
    else:
        plugin.config["settings"].update(payload)
        await asyncio.to_thread(save_widget_settings, widget_id, plugin.config["settings"])
    # Force the next summary/detail request to reflect the new settings
    # instead of serving a stale cached response. Every cache entry for this
    # widget starts with "{kind}:{widget_id}:" (locale is always appended,
    # plus user/device for scoped plugins), so a single prefix sweep per
    # kind catches every variant regardless of scope.
    cache.delete_prefix(f"summary:{widget_id}:")
    cache.delete_prefix(f"detail:{widget_id}:")
    if isinstance(plugin, PhotosPlugin) and _PHOTO_INDEX_RELEVANT_SETTINGS & payload.keys():
        schedule_photo_index(plugin)
    elif isinstance(plugin, SpeedtestPlugin) and "interval_minutes" in payload:
        schedule_speedtest_widget(plugin)
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
    cache.delete_prefix(_cache_key_prefix("summary", plugin, user, device))
    cache.delete_prefix(_cache_key_prefix("detail", plugin, user, device))
    return merged


@router.delete("/{widget_id}/device-settings")
async def clear_widget_device_settings_route(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)
    await asyncio.to_thread(delete_widget_device_settings, device["id"], widget_id)
    cache.delete_prefix(_cache_key_prefix("summary", plugin, user, device))
    cache.delete_prefix(_cache_key_prefix("detail", plugin, user, device))
    return {"status": "ok"}


@router.post("/{widget_id}/run")
async def run_widget_now(widget_id: str, user: dict[str, Any] = Depends(get_current_user)):
    plugin = _get_plugin(widget_id)
    if isinstance(plugin, AIInsightsPlugin):
        await run_ai_widget(plugin)
    elif isinstance(plugin, SpeedtestPlugin):
        await run_speedtest_widget(plugin)
    else:
        raise HTTPException(status_code=400, detail=f"Widget '{widget_id}' cannot be run on demand")

    cache.delete_prefix(f"summary:{widget_id}:")
    cache.delete_prefix(f"detail:{widget_id}:")

    data = await plugin.get_detail()
    # Neither AI-generated text nor speedtest numbers are locale-translated
    # (see TODO.md), so this always runs at the base singleton's default
    # locale ("en") — cache it under that same key so an "en"-locale GET
    # request can reuse it; other locales simply miss and recompute, same as
    # before this endpoint had a dedicated pre-warm at all.
    cache.set(f"detail:{widget_id}:en", data, plugin.refresh_interval_seconds)
    return data


@router.delete("/{widget_id}")
async def remove_widget(widget_id: str, user: dict[str, Any] = Depends(get_current_user)):
    plugin = _get_plugin(widget_id)
    require_write_access(plugin, user)

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
    cache.delete_prefix(f"summary:{widget_id}:")
    cache.delete_prefix(f"detail:{widget_id}:")
    return {"status": "ok"}
