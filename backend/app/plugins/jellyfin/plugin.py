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

import logging
from typing import Any

from app.i18n import t
from app.integrations import jellyfin_client
from app.plugins.base import Plugin

logger = logging.getLogger(__name__)


class JellyfinPlugin(Plugin):
    id = "jellyfin"
    name = "Jellyfin"
    refresh_interval_seconds = 600
    network_integration_type = "jellyfin"
    network_default_settings = {
        "host": "",
        "port": 8096,
        "use_https": False,
        "auth_mode": "api_key",  # "api_key" | "password"
        "api_key": "",
        "username": "",
        "password": "",
    }
    default_settings = {
        "library_ids": [],  # optional filter; empty = show all libraries
        # "added" | "played" | "both" — which section(s) the tile/detail show.
        # "played" (Continue Watching) needs a real user context, which
        # api_key auth doesn't have — see resume_available below.
        "content_mode": "added",
    }
    default_layout = {"colSpan": 2, "rowSpan": 1}
    secret_setting_keys = frozenset({"api_key", "password"})

    def _safe_settings(self) -> dict[str, Any]:
        return {
            **super()._safe_settings(),
            # Continue Watching needs a real user context (see
            # jellyfin_client.list_resume_items) — the frontend uses this to
            # disable "played"/"both" rather than silently showing nothing.
            "resume_available": self.config["settings"].get("auth_mode") == "password",
        }

    def _is_connected(self) -> bool:
        return jellyfin_client.is_configured(self.config["settings"])

    async def _fetch_sections(self) -> list[dict[str, Any]]:
        settings = self.config["settings"]
        content_mode = settings.get("content_mode", "added")
        sections: list[dict[str, Any]] = []

        if content_mode in ("added", "both"):
            try:
                added = await jellyfin_client.list_recent_items(settings, self.id)
            except jellyfin_client.JellyfinError:
                logger.warning("Could not fetch recent items for widget '%s'", self.id, exc_info=True)
                added = []
            sections.append({"label": t("jellyfin.section.recently_added", self.locale), "items": added})

        if content_mode in ("played", "both"):
            try:
                played = await jellyfin_client.list_resume_items(settings, self.id)
            except jellyfin_client.JellyfinError:
                logger.warning("Could not fetch resume items for widget '%s'", self.id, exc_info=True)
                played = []
            sections.append({"label": t("jellyfin.section.continue_watching", self.locale), "items": played})

        return sections

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        sections: list[dict[str, Any]] = await self._fetch_sections() if connected else []
        return {"connected": connected, "sections": sections, **self._safe_settings()}

    async def get_detail(self) -> dict[str, Any]:
        return {"connected": self._is_connected(), **self._safe_settings()}
