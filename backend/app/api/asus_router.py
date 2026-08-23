"""Asus router device actions and diagnostics API.

Provides endpoints for on-demand port scanning, web UI launching detection,
Wake-on-LAN (WOL), client internet access control, friendly name/alias assignment,
static DHCP reservations, and ping latency checks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_write_access
from app.integrations import asus_router_client
from app.plugins.asus_router.plugin import AsusRouterPlugin
from app.plugins.base import get_typed_plugin

router = APIRouter(prefix="/api/asus-router", tags=["asus-router"], dependencies=[Depends(get_current_user)])


def _get_plugin(widget_id: str) -> AsusRouterPlugin:
    return get_typed_plugin(widget_id, AsusRouterPlugin, "Asus Router")


class ScanPortsRequest(BaseModel):
    ip: str = Field(..., description="Target LAN IP address")
    ports: list[int] | None = Field(default=None, description="Optional custom ports to scan")


class WakeOnLanRequest(BaseModel):
    mac: str = Field(..., description="Target device MAC address")


class ClientBlockRequest(BaseModel):
    mac: str = Field(..., description="Target device MAC address")
    blocked: bool = Field(..., description="Whether to block internet access")


class ClientAliasRequest(BaseModel):
    mac: str = Field(..., description="Target device MAC address")
    alias: str = Field(..., description="Custom device name or alias")


class StaticLeaseRequest(BaseModel):
    mac: str = Field(..., description="Target device MAC address")
    ip: str = Field(..., description="Reserved IP address")
    name: str = Field(default="", description="Hostname or alias for static lease")
    enabled: bool = Field(..., description="Whether static lease is active")


class PingRequest(BaseModel):
    ip: str = Field(..., description="Target LAN IP address")


@router.post("/{widget_id}/scan-ports")
async def scan_ports(
    widget_id: str,
    payload: ScanPortsRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    _get_plugin(widget_id)
    try:
        return await asus_router_client.scan_client_ports(payload.ip, payload.ports)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Port scan failed: {exc}") from exc


@router.post("/{widget_id}/wake-on-lan")
async def wake_on_lan(
    widget_id: str,
    payload: WakeOnLanRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    plugin = _get_plugin(widget_id)
    try:
        return await asus_router_client.send_wake_on_lan(plugin.config["settings"], payload.mac)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send Wake-on-LAN: {exc}") from exc


@router.post("/{widget_id}/client-block")
async def set_client_block(
    widget_id: str,
    payload: ClientBlockRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    plugin = _get_plugin(widget_id)
    require_write_access(plugin, user)
    try:
        return await asus_router_client.set_client_internet_block(
            plugin.config["settings"], widget_id, payload.mac, payload.blocked
        )
    except asus_router_client.AsusRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{widget_id}/client-alias")
async def set_client_alias(
    widget_id: str,
    payload: ClientAliasRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    plugin = _get_plugin(widget_id)
    require_write_access(plugin, user)
    try:
        return await asus_router_client.set_client_alias(
            plugin.config["settings"], widget_id, payload.mac, payload.alias
        )
    except asus_router_client.AsusRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{widget_id}/dhcp-static-lease")
async def set_dhcp_static_lease(
    widget_id: str,
    payload: StaticLeaseRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    plugin = _get_plugin(widget_id)
    require_write_access(plugin, user)
    try:
        return await asus_router_client.set_dhcp_static_reservation(
            plugin.config["settings"], widget_id, payload.mac, payload.ip, payload.name, payload.enabled
        )
    except asus_router_client.AsusRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{widget_id}/ping")
async def ping_device(
    widget_id: str,
    payload: PingRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    plugin = _get_plugin(widget_id)
    try:
        return await asus_router_client.ping_client(payload.ip, plugin.config["settings"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ping check failed: {exc}") from exc
