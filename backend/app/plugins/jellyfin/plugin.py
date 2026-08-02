"""Jellyfin plugin: browse a Jellyfin media server's libraries and play
video directly in the dashboard.

Connects via either a server-issued API key or a real user's
username/password (see `app/integrations/jellyfin_client.py`); the widget's
detail view browses libraries and streams video through
`app/api/jellyfin.py`'s proxy routes, so credentials never reach the
browser. Until connected, get_summary/get_detail return an empty,
not-connected state rather than raising, so the widget degrades gracefully.
"""

from __future__ import annotations

from typing import Any

from app.integrations import jellyfin_client
from app.plugins.base import Plugin


class JellyfinPlugin(Plugin):
    id = "jellyfin"
    name = "Jellyfin"
    refresh_interval_seconds = 600
    default_settings = {
        "host": "",
        "port": 8096,
        "use_https": False,
        "auth_mode": "api_key",  # "api_key" | "password"
        "api_key": "",
        "username": "",
        "password": "",
        "library_ids": [],  # optional filter; empty = show all libraries
        "playback_mode": "compatible",  # "compatible" | "direct" — see jellyfin_client.open_video_stream
    }
    default_layout = {"colSpan": 2, "rowSpan": 1}

    def _safe_settings(self) -> dict[str, Any]:
        # Secrets are write-only: callers get a boolean "is it set", never
        # the raw value, since the generic settings PATCH endpoint echoes
        # this plugin's own config verbatim — masking has to happen here.
        s = self.config["settings"]
        return {
            "host": s.get("host", ""),
            "port": s.get("port", 8096),
            "use_https": bool(s.get("use_https", False)),
            "auth_mode": s.get("auth_mode", "api_key"),
            "username": s.get("username", ""),
            "library_ids": s.get("library_ids") or [],
            "playback_mode": s.get("playback_mode", "compatible"),
            "has_api_key": bool(s.get("api_key")),
            "has_password": bool(s.get("password")),
        }

    def _is_connected(self) -> bool:
        return jellyfin_client.is_configured(self.config["settings"])

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        recent_items: list[dict[str, Any]] = []
        if connected:
            try:
                recent_items = await jellyfin_client.list_recent_items(self.config["settings"], self.id)
            except jellyfin_client.JellyfinError:
                recent_items = []
        return {"connected": connected, "recent_items": recent_items, **self._safe_settings()}

    async def get_detail(self) -> dict[str, Any]:
        return {"connected": self._is_connected(), **self._safe_settings()}
