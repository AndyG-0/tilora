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
from app.plugins.naming import display_names
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
from app.storage.cache import cache, cached_call, user_locale_cache_key
from app.storage.db import (
    clear_widget_custom_name,
    delete_custom_widget,
    delete_hidden_widget_ids_for_widget,
    delete_photo_index,
    delete_widget_device_settings,
    delete_widget_device_settings_for_widget,
    delete_widget_layout_for_widget,
    delete_widget_user_settings_for_widget,
    get_user_preferences,
    get_widget_device_settings,
    get_widget_user_settings,
    hidden_widget_ids,
    hide_widget,
    list_custom_widgets,
    list_widget_layouts,
    save_custom_widget,
    save_widget_custom_name,
    save_widget_device_settings,
    save_widget_layouts,
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


def _widget_is_visible(widget: dict[str, Any], user_id: str, device_id: str, hidden: set[str]) -> bool:
    owner_user_id = widget.get("owner_user_id")
    owner_device_id = widget.get("owner_device_id")
    if owner_user_id is not None or owner_device_id is not None:
        # A UI-added widget created after ownership tracking existed:
        # private to the (user, device) pair that created it.
        return owner_user_id == user_id and owner_device_id == device_id
    # A dashboard.yaml widget, or a legacy pre-ownership custom widget:
    # visible to everyone by default, opt-out per (user, device).
    return widget["id"] not in hidden


def _list_widgets_sync(user_id: str, device_id: str, breakpoint: Breakpoint) -> list[dict[str, Any]]:
    config = load_dashboard_config()
    default_tab = resolve_tabs(config)[0]["id"]
    layouts = list_widget_layouts(user_id, device_id, breakpoint)
    hidden = hidden_widget_ids(user_id, device_id)
    visible = [
        w
        for w in list_widget_configs(config)
        if w.get("enabled", True) and _widget_is_visible(w, user_id, device_id, hidden)
    ]
    # Not every visible config entry has a live registry plugin yet (e.g. a
    # config referencing a type that failed to load) — display_names only
    # needs the ones that do, and a widget with no plugin falls back to its
    # bare type string below.
    plugins = [registry.get(w["id"]) for w in visible]
    names = display_names([p for p in plugins if p is not None])
    plugins_by_id = {w["id"]: p for w, p in zip(visible, plugins, strict=True) if p is not None}
    return [
        {
            "id": w["id"],
            "type": w["type"],
            "name": names.get(w["id"], w["type"]),
            # A drag-to-rearrange edit persisted at runtime overrides the
            # dashboard.yaml position, scoped to this (user, device,
            # breakpoint) triple — the same layering pattern widget settings
            # overrides use, just with two extra dimensions.
            "layout": {**w["layout"], **layouts.get(w["id"], {})},
            "tab": w.get("tab", default_tab),
            # Lets the frontend poll each tile at the same cadence its data
            # actually refreshes at, instead of a fixed interval unrelated to
            # this widget's cache TTL. Falls back to a sane default for the
            # rare config entry with no live plugin registered.
            "refresh_interval_seconds": (
                plugins_by_id[w["id"]].refresh_interval_seconds if w["id"] in plugins_by_id else 300
            ),
        }
        for w in visible
    ]


@router.get("")
async def list_widgets(
    breakpoint: Breakpoint,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    # One thread hop for the whole list (config-file read + one bulk layout
    # query) rather than one per widget — cheaper than to_thread-per-call
    # and this whole read is what needs to move off the event loop, not each
    # individual piece of it.
    return await asyncio.to_thread(_list_widgets_sync, user["id"], device["id"], breakpoint)


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
    entries = [
        (user["id"], device["id"], payload.breakpoint, entry.id, entry.layout.model_dump()) for entry in payload.widgets
    ]
    await asyncio.to_thread(save_widget_layouts, entries)
    return {"status": "ok"}


@router.post("")
async def add_widget(
    payload: AddWidgetRequest,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin_cls = PLUGIN_CLASSES_BY_TYPE.get(payload.type)
    if plugin_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown widget type '{payload.type}'")
    # No real plugin instance exists yet, and settings_scope isn't always a
    # plain ClassVar (PhotosPlugin's depends on its own settings — see its
    # docstring), so a throwaway instance seeded with this type's starter
    # settings is built just to read it correctly, rather than reading the
    # class attribute directly.
    throwaway = plugin_cls({"id": "", "settings": dict(plugin_cls.default_settings)})
    if throwaway.settings_scope == "network" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    widget_id = f"{payload.type}-{uuid4().hex[:8]}"
    while registry.get(widget_id) is not None:
        widget_id = f"{payload.type}-{uuid4().hex[:8]}"

    layout = payload.layout.model_dump()
    tab = payload.tab
    settings = dict(plugin_cls.default_settings)

    await asyncio.to_thread(save_custom_widget, widget_id, payload.type, layout, tab, user["id"], device["id"])
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
    siblings = [p for p in registry.all() if type(p) is plugin_cls]
    name = display_names(siblings)[widget_id]
    return {
        "id": widget_id,
        "type": payload.type,
        "name": name,
        "layout": layout,
        "tab": tab or default_tab,
        "refresh_interval_seconds": plugin.refresh_interval_seconds,
    }


def _get_plugin(widget_id: str):
    plugin = registry.get(widget_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Unknown widget '{widget_id}'")
    return plugin


# How long a resolved locale is cached for, keyed by user id — avoids a DB
# round-trip on every summary/detail poll (including cache *hits*, which
# otherwise still paid for this lookup before ever checking the cache).
# update_preferences() (see app.api.users) invalidates this immediately on
# a locale change, so the TTL only bounds staleness from writes made
# outside that endpoint, not normal user-facing latency.
_LOCALE_CACHE_TTL_SECONDS = 3600


async def _user_locale(user_id: str) -> str:
    async def fetch() -> str:
        prefs = await asyncio.to_thread(get_user_preferences, user_id)
        return prefs.get("locale", "en")

    return await cached_call(user_locale_cache_key(user_id), _LOCALE_CACHE_TTL_SECONDS, fetch)


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
    locale = await _user_locale(user["id"])
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
    locale = await _user_locale(user["id"])
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

    # settings_scope may depend on the plugin's own settings (PhotosPlugin's
    # does — see its docstring), so it's read off a throwaway instance
    # carrying the settings this payload would produce, not the plugin's
    # current (pre-patch) settings. Otherwise a payload that changes scope
    # (e.g. Photos switching provider between "local"/"icloud_private")
    # would be access-gated by the tier its *old* settings belonged to
    # instead of its new ones — see app.api.widgets.add_widget, which has
    # the same need.
    prospective = plugin.with_settings({**plugin.config["settings"], **payload})
    # PhotosPlugin's `provider` (and everything else the background indexer
    # keys off, see _PHOTO_INDEX_RELEVANT_SETTINGS) has to stay a single
    # shared value no matter who changes it — both the indexer
    # (app.plugins.photos.indexer.index_photos) and every other viewer's
    # reads (app.plugins.scoping.scoped_plugin) key off the registry
    # singleton's live settings, not a per-user override, so a value stored
    # only in widget_user_settings would silently never take effect. So
    # unlike every other personal-scope plugin, Photos never takes the
    # per-user storage branch below — "personal" here (switching *to*
    # icloud_private, a viewer connecting their own account) only means the
    # admin gate a couple lines down is skipped, not that the value is
    # scoped per-user.
    if prospective.settings_scope == "personal" and not isinstance(plugin, PhotosPlugin):
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

    if prospective.settings_scope == "network":
        require_write_access(prospective, user)
    # else: PhotosPlugin settling into (or staying in) "personal" scope —
    # no admin gate, but still falls through to the shared-tier write below.
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


class RenameWidgetRequest(BaseModel):
    name: str


@router.patch("/{widget_id}/name")
async def rename_widget(
    widget_id: str,
    payload: RenameWidgetRequest,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    # Display metadata, not plugin connection config, so unlike
    # update_widget_settings this isn't gated behind require_write_access —
    # any household member may relabel a shared tile for their own clarity.
    plugin = _get_plugin(widget_id)
    trimmed = payload.name.strip()
    if len(trimmed) > 60:
        raise HTTPException(status_code=400, detail="Name must be 60 characters or fewer")

    if trimmed:
        await asyncio.to_thread(save_widget_custom_name, widget_id, trimmed)
    else:
        await asyncio.to_thread(clear_widget_custom_name, widget_id)
    siblings = [p for p in registry.all() if type(p) is type(plugin)]
    return {"id": widget_id, "name": trimmed or display_names(siblings)[widget_id]}


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
async def remove_widget(
    widget_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    plugin = _get_plugin(widget_id)

    custom_widgets = {w["id"]: w for w in await asyncio.to_thread(list_custom_widgets)}
    custom = custom_widgets.get(widget_id)
    owned = custom is not None and custom["owner_user_id"] == user["id"] and custom["owner_device_id"] == device["id"]

    if not owned:
        # A shared default (dashboard.yaml or legacy-global custom widget),
        # or a widget owned by a different (user, device) pair — can't be
        # deleted outright. Just hide it from this (user, device)'s own
        # list; any household member may declutter their own screen.
        await asyncio.to_thread(hide_widget, user["id"], device["id"], widget_id)
        return {"status": "hidden"}

    require_write_access(plugin, user)
    await asyncio.to_thread(delete_custom_widget, widget_id)
    await asyncio.to_thread(delete_widget_layout_for_widget, widget_id)
    await asyncio.to_thread(delete_widget_user_settings_for_widget, widget_id)
    await asyncio.to_thread(delete_widget_device_settings_for_widget, widget_id)
    await asyncio.to_thread(delete_hidden_widget_ids_for_widget, widget_id)
    await asyncio.to_thread(clear_widget_custom_name, widget_id)

    registry.unregister(widget_id)
    unschedule_widget(widget_id)
    if isinstance(plugin, PhotosPlugin):
        await asyncio.to_thread(delete_photo_index, widget_id)
    cache.delete_prefix(f"summary:{widget_id}:")
    cache.delete_prefix(f"detail:{widget_id}:")
    return {"status": "ok"}
