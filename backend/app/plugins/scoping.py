"""Resolves the plugin instance a given (user, device) should read from.

Shared by the widget REST endpoints (`app.api.widgets`) and the AI assistant
(`app.ai.assistant`), so voice/text queries see the same personalized
settings as the dashboard tile instead of falling back to the registry
singleton's base config.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.plugins.base import Plugin
from app.storage.db import get_widget_device_settings, get_widget_user_settings


async def scoped_plugin(plugin: Plugin, user: dict[str, Any], device: dict[str, Any]) -> Plugin:
    """The plugin instance to read from for this (user, device).

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
