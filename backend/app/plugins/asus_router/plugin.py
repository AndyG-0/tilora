"""Asus Router plugin: connected-client count and WAN status from an
AsusWRT/Merlin router (see `app/integrations/asus_router_client.py` for the
token-auth flow against the router's `appGet.cgi` hook interface).

Connects via a router admin account's username/password; until connected,
get_summary/get_detail return a not-connected state rather than raising, so
the widget degrades gracefully.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.integrations import asus_router_client
from app.plugins.base import Plugin, ToolDef


class AsusRouterPlugin(Plugin):
    id = "asus_router"
    name = "Asus Router"
    refresh_interval_seconds = 30
    default_settings: ClassVar[dict[str, Any]] = {
        "host": "",
        "port": 443,
        "use_https": True,
        "username": "",
        "password": "",
    }

    def _safe_settings(self) -> dict[str, Any]:
        s = self.config["settings"]
        return {
            "host": s.get("host", ""),
            "port": s.get("port", 443),
            "use_https": bool(s.get("use_https", True)),
            "username": s.get("username", ""),
            "has_password": bool(s.get("password")),
        }

    def _is_connected(self) -> bool:
        return asus_router_client.is_configured(self.config["settings"])

    async def _wan_and_clients(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
        if not self._is_connected():
            return None, [], None
        try:
            wan = await asus_router_client.get_wan_status(self.config["settings"], self.id)
            clients = await asus_router_client.get_clients(self.config["settings"], self.id)
        except asus_router_client.AsusRouterError as exc:
            return None, [], str(exc)
        return wan, clients, None

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        wan, clients, error = await self._wan_and_clients()
        result: dict[str, Any] = {
            "connected": connected,
            "wan_connected": wan["connected"] if wan else False,
            "client_count": len(clients),
            **self._safe_settings(),
        }
        if error:
            result["error"] = error
        return result

    @staticmethod
    def _empty_detail_fields() -> dict[str, Any]:
        return {"wan_ip": None, "clients": [], "rx_bytes": 0, "tx_bytes": 0}

    async def get_detail(self) -> dict[str, Any]:
        summary = await self.get_summary()
        if not summary["connected"] or summary.get("error"):
            return {**summary, **self._empty_detail_fields()}

        wan, clients, error = await self._wan_and_clients()
        if error:
            return {**summary, "error": error, **self._empty_detail_fields()}

        try:
            traffic = await asus_router_client.get_traffic(self.config["settings"], self.id)
        except asus_router_client.AsusRouterError as exc:
            return {
                **summary,
                "error": str(exc),
                "wan_ip": wan["ip"] if wan else None,
                "clients": clients,
                "rx_bytes": 0,
                "tx_bytes": 0,
            }

        return {
            **summary,
            "wan_ip": wan["ip"] if wan else None,
            "clients": clients,
            **traffic,
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_asus_router_status() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_asus_router_status",
                description="Get the Asus router's WAN connection status, the number of connected "
                "clients, and whether the router is currently reachable.",
                parameters={"type": "object", "properties": {}},
                handler=get_asus_router_status,
            )
        ]
