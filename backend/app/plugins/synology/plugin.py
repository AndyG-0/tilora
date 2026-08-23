"""Synology plugin: storage volume usage and basic system info from a
Synology DSM NAS (see `app/integrations/synology_client.py` for the
session-auth flow against DSM's Web API).

Connects via a DSM user account's username/password; until connected,
get_summary/get_detail return a not-connected state rather than raising, so
the widget degrades gracefully.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.integrations import synology_client
from app.plugins.base import Plugin, ToolDef

_LOGGER = logging.getLogger(__name__)


class SynologyPlugin(Plugin):
    id = "synology"
    name = "Synology"
    refresh_interval_seconds = 60
    network_integration_type = "synology"
    network_default_settings: ClassVar[dict[str, Any]] = {
        "host": "",
        "port": 5000,
        "use_https": False,
        "username": "",
        "password": "",
    }
    secret_setting_keys: ClassVar[frozenset[str]] = frozenset({"password"})

    def _is_connected(self) -> bool:
        return synology_client.is_configured(self.config["settings"])

    async def _volumes(self) -> tuple[list[dict[str, Any]], str | None]:
        if not self._is_connected():
            return [], None
        try:
            volumes = await synology_client.get_storage(self.config["settings"], self.id)
        except synology_client.SynologyError as exc:
            _LOGGER.warning("Could not fetch storage volumes for widget '%s': %s", self.id, exc)
            return [], str(exc)
        return volumes, None

    def _build_summary(self, connected: bool, volumes: list[dict[str, Any]], error: str | None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "connected": connected,
            "volumes": [{"name": v["name"], "used_percent": v["used_percent"], "status": v["status"]} for v in volumes],
            **self._safe_settings(),
        }
        if error:
            result["error"] = error
        return result

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        volumes, error = await self._volumes()
        return self._build_summary(connected, volumes, error)

    @staticmethod
    def _empty_system_info() -> dict[str, Any]:
        return {"model": None, "uptime": None, "temperature_celsius": None}

    async def get_detail(self) -> dict[str, Any]:
        connected = self._is_connected()
        volumes, error = await self._volumes()
        summary = self._build_summary(connected, volumes, error)
        if not connected or error:
            return {**summary, "volumes": [], **self._empty_system_info()}

        try:
            system_info = await synology_client.get_system_info(self.config["settings"], self.id)
        except synology_client.SynologyError as exc:
            _LOGGER.warning("Could not fetch system info for widget '%s': %s", self.id, exc)
            return {**summary, "error": str(exc), "volumes": volumes, **self._empty_system_info()}

        if system_info.get("temperature_celsius") is None:
            # DSM's SYNO.Core.System.info often withholds CPU temperature
            # from non-admin accounts rather than returning an error — this
            # is the only signal we get, so log it for diagnosability.
            _LOGGER.debug(
                "Synology system info fetched successfully but temperature_celsius was missing "
                "(widget_id=%s) — DSM may be withholding it from a non-admin account.",
                self.id,
            )

        return {**summary, "volumes": volumes, **system_info}

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_synology_storage_status() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_synology_storage_status",
                description="Get the Synology NAS's storage volumes, each volume's used percentage "
                "and health status, and whether the NAS is currently reachable.",
                parameters={"type": "object", "properties": {}},
                handler=get_synology_storage_status,
            )
        ]
