"""Pi-hole plugin: DNS query/blocking stats from a Pi-hole v6 instance, with
a control to pause or re-enable blocking.

Connects via the admin/app password (see `app/integrations/pihole_client.py`
for the session-auth flow); until connected, get_summary/get_detail return a
not-connected state rather than raising, so the widget degrades gracefully.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations import pihole_client
from app.plugins.base import Plugin, ToolDef

logger = logging.getLogger(__name__)

_TOP_DOMAINS_COUNT = 5


class PiholePlugin(Plugin):
    id = "pihole"
    name = "Pi-hole"
    refresh_interval_seconds = 60
    network_integration_type = "pihole"
    network_default_settings = {
        "host": "",
        "port": 80,
        "use_https": False,
        "password": "",
    }
    secret_setting_keys = frozenset({"password"})

    def _is_connected(self) -> bool:
        return pihole_client.is_configured(self.config["settings"])

    async def _stats(self) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Returns (summary fields, raw get_summary_stats() response).

        The raw response is returned alongside the derived summary fields so
        get_detail() can pull its extra fields (clients, gravity) from it
        without a second `get_summary_stats` round-trip — it's None only
        when the fetch itself failed, in which case the summary dict is
        just `{"error": ...}`.
        """
        settings = self.config["settings"]
        try:
            raw_summary = await pihole_client.get_summary_stats(settings, self.id)
            blocking = await pihole_client.get_blocking_status(settings, self.id)
        except pihole_client.PiholeError as exc:
            logger.warning("Could not fetch Pi-hole stats for widget '%s': %s", self.id, exc)
            return {"error": str(exc)}, None

        queries = raw_summary.get("queries") or {}
        return {
            "blocking_enabled": blocking.get("blocking") == "enabled",
            "blocking_timer": blocking.get("timer"),
            "queries_today": queries.get("total", 0),
            "blocked_today": queries.get("blocked", 0),
            "percent_blocked": queries.get("percent_blocked", 0),
        }, raw_summary

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        stats: dict[str, Any] = {}
        if connected:
            stats, _ = await self._stats()
        return {"connected": connected, **stats, **self._safe_settings()}

    @staticmethod
    def _empty_detail_fields() -> dict[str, Any]:
        return {
            "unique_clients": 0,
            "clients_total": 0,
            "domains_blocked": 0,
            "gravity_last_update": None,
            "top_blocked_domains": [],
            "top_permitted_domains": [],
        }

    async def get_detail(self) -> dict[str, Any]:
        connected = self._is_connected()
        if not connected:
            return {"connected": False, **self._safe_settings(), **self._empty_detail_fields()}

        stats, raw_summary = await self._stats()
        summary = {"connected": connected, **stats, **self._safe_settings()}
        if raw_summary is None:
            return {**summary, **self._empty_detail_fields()}

        settings = self.config["settings"]
        try:
            top_blocked = await pihole_client.get_top_domains(settings, self.id, blocked=True, count=_TOP_DOMAINS_COUNT)
            top_permitted = await pihole_client.get_top_domains(
                settings, self.id, blocked=False, count=_TOP_DOMAINS_COUNT
            )
        except pihole_client.PiholeError as exc:
            logger.warning("Could not fetch Pi-hole detail stats for widget '%s': %s", self.id, exc)
            return {**summary, "error": str(exc), **self._empty_detail_fields()}

        clients = raw_summary.get("clients") or {}
        gravity = raw_summary.get("gravity") or {}
        return {
            **summary,
            "unique_clients": clients.get("active", 0),
            "clients_total": clients.get("total", 0),
            "domains_blocked": gravity.get("domains_being_blocked", 0),
            "gravity_last_update": gravity.get("last_update"),
            "top_blocked_domains": top_blocked,
            "top_permitted_domains": top_permitted,
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_pihole_summary() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_pihole_summary",
                description="Get today's Pi-hole DNS query stats: total queries, blocked count, "
                "percent blocked, and whether blocking is currently enabled.",
                parameters={"type": "object", "properties": {}},
                handler=get_pihole_summary,
            )
        ]
