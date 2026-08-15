"""Asus Router plugin: connected-client count and WAN status from an
AsusWRT/Merlin router, read over SSH (see
`app/integrations/asus_router_client.py` for why SSH rather than the
router's web-UI login, and for the `nvram`/`/proc` data it reads).

Connects via a router admin account's username/password over SSH; until
connected, get_summary/get_detail return a not-connected state rather than
raising, so the widget degrades gracefully.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.integrations import asus_router_client
from app.plugins.base import Plugin, ToolDef

logger = logging.getLogger(__name__)


class AsusRouterPlugin(Plugin):
    id = "asus_router"
    name = "Asus Router"
    refresh_interval_seconds = 30
    network_integration_type = "asus_router"
    network_default_settings: ClassVar[dict[str, Any]] = {
        "host": "",
        "ssh_port": 22,
        "username": "",
        "password": "",
    }

    def _safe_settings(self) -> dict[str, Any]:
        s = self.config["settings"]
        return {
            "host": s.get("host", ""),
            "ssh_port": s.get("ssh_port", 22),
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
            logger.warning("Could not fetch WAN status/clients for widget '%s': %s", self.id, exc)
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
            logger.warning("Could not fetch traffic stats for widget '%s': %s", self.id, exc)
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

        async def get_asus_router_clients() -> list[dict[str, Any]]:
            if not self._is_connected():
                return []
            return await asus_router_client.get_clients(self.config["settings"], self.id)

        async def send_wake_on_lan(mac: str) -> dict[str, Any]:
            return await asus_router_client.send_wake_on_lan(self.config["settings"], mac)

        return [
            ToolDef(
                name="get_asus_router_status",
                description="Get the Asus router's WAN connection status, the number of connected "
                "clients, and whether the router is currently reachable.",
                parameters={"type": "object", "properties": {}},
                handler=get_asus_router_status,
            ),
            ToolDef(
                name="get_asus_router_clients",
                description="Get the list of connected clients on the Asus router, including IP, "
                "MAC address, wired/wireless connection type, and signal information.",
                parameters={"type": "object", "properties": {}},
                handler=get_asus_router_clients,
            ),
            ToolDef(
                name="asus_router_wake_on_lan",
                description="Send a Wake-on-LAN (WOL) magic packet to a device's MAC address via the router.",
                parameters={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "The MAC address of the target device to wake (e.g. '00:11:22:33:44:55')",
                        }
                    },
                    "required": ["mac"],
                },
                handler=send_wake_on_lan,
            ),
        ]
