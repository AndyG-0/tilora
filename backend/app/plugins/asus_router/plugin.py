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

_DEFAULT_POLL_INTERVAL_SECONDS = 60
# Matches asus_router_client._STATUS_TTL_SECONDS — below that, a lower poll
# interval wouldn't actually poll any more often, just skip the cache.
_MIN_POLL_INTERVAL_SECONDS = 20


class AsusRouterPlugin(Plugin):
    id = "asus_router"
    name = "Asus Router"
    network_integration_type = "asus_router"
    default_settings: ClassVar[dict[str, Any]] = {"poll_interval_seconds": _DEFAULT_POLL_INTERVAL_SECONDS}
    network_default_settings: ClassVar[dict[str, Any]] = {
        "host": "",
        "ssh_port": 22,
        "username": "",
        "password": "",
    }
    secret_setting_keys: ClassVar[frozenset[str]] = frozenset({"password"})

    @property
    def refresh_interval_seconds(self) -> int:
        raw = self.config["settings"].get("poll_interval_seconds", _DEFAULT_POLL_INTERVAL_SECONDS)
        try:
            seconds = int(raw)
        except (TypeError, ValueError):
            return _DEFAULT_POLL_INTERVAL_SECONDS
        return max(_MIN_POLL_INTERVAL_SECONDS, seconds)

    def validate_settings(self, payload: dict[str, Any]) -> None:
        if "poll_interval_seconds" in payload:
            try:
                seconds = int(payload["poll_interval_seconds"])
            except (TypeError, ValueError) as exc:
                raise ValueError("poll_interval_seconds must be a whole number of seconds") from exc
            if seconds < _MIN_POLL_INTERVAL_SECONDS:
                raise ValueError(f"poll_interval_seconds must be at least {_MIN_POLL_INTERVAL_SECONDS}")

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

    def _build_summary(
        self, connected: bool, wan: dict[str, Any] | None, clients: list[dict[str, Any]], error: str | None
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "connected": connected,
            "wan_connected": wan["connected"] if wan else False,
            "client_count": len(clients),
            **self._safe_settings(),
        }
        if error:
            result["error"] = error
        return result

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        wan, clients, error = await self._wan_and_clients()
        return self._build_summary(connected, wan, clients, error)

    @staticmethod
    def _empty_detail_fields() -> dict[str, Any]:
        return {"wan_ip": None, "clients": [], "rx_bytes": 0, "tx_bytes": 0}

    async def get_detail(self) -> dict[str, Any]:
        connected = self._is_connected()
        wan, clients, error = await self._wan_and_clients()
        summary = self._build_summary(connected, wan, clients, error)
        if not connected or error:
            return {**summary, **self._empty_detail_fields()}

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
                requires_admin=True,
            ),
        ]
