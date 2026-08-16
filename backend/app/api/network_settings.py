"""Network-level integration settings: one shared, admin-edited connection
config per physical LAN device (Pi-hole, Jellyfin, Synology, Asus Router,
HDHomeRun — one row each — or a named Docker/Podman host, multiple rows)
instead of the old per-widget-instance settings. See
`app.plugins.network_settings` for how a saved row here propagates live into
every plugin instance that uses it.

Reads are open to any logged-in user (same as widget summary/detail);
writes require admin, matching `require_write_access`'s treatment of
`settings_scope == "network"` for these same plugin types.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_admin, get_current_user
from app.integrations import (
    asus_router_client,
    container_client,
    hdhomerun_client,
    jellyfin_client,
    pihole_client,
    synology_client,
)
from app.plugins.base import registry
from app.plugins.container.plugin import ContainerPlugin
from app.plugins.network_settings import apply_network_integration_update
from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE
from app.storage.cache import cache
from app.storage.db import (
    NETWORK_INTEGRATION_SECRET_KEYS,
    delete_network_integration,
    get_network_integration,
    list_network_integrations,
    save_network_integration,
)

router = APIRouter(prefix="/api/network-settings", tags=["network-settings"], dependencies=[Depends(get_current_user)])

_TEST_CONNECTION_ERRORS = (
    pihole_client.PiholeError,
    jellyfin_client.JellyfinError,
    synology_client.SynologyError,
    asus_router_client.AsusRouterError,
    hdhomerun_client.HDHomeRunError,
    container_client.ContainerError,
)

# Singleton types only — HDHomeRun has its own two test-connection routes
# below (tuner and DVR are independent devices), and Container hosts are
# tested per-id via /container/{id}/test-connection instead.
_TEST_CONNECTION_DISPATCH: dict[str, Callable[[dict[str, Any], str], Awaitable[str]]] = {
    "pihole": pihole_client.test_connection,
    "jellyfin": jellyfin_client.test_connection,
    "synology": synology_client.test_connection,
    "asus_router": asus_router_client.test_connection,
}


def _mask(settings: dict[str, Any]) -> dict[str, Any]:
    # Secrets are write-only in every API response — callers get a boolean
    # "is it set", never the raw value, same pattern each plugin's old
    # `_safe_settings()` used for its own per-widget settings.
    masked: dict[str, Any] = {}
    for key, value in settings.items():
        if key in NETWORK_INTEGRATION_SECRET_KEYS:
            masked[f"has_{key}"] = bool(value)
        else:
            masked[key] = value
    return masked


def _invalidate(affected: list[str], integration_type: str | None = None) -> None:
    targets = set(affected)
    if integration_type:
        targets.add(integration_type)
    for target in targets:
        cache.delete_prefix(f"summary:{target}:")
        cache.delete_prefix(f"detail:{target}:")
        cache.delete(f"pihole_sid:{target}")
        cache.delete(f"jellyfin_token:{target}")
        cache.delete(f"synology_sid:{target}")
        cache.delete(f"qbittorrent_sid:{target}")


def _singleton_plugin_cls(type_: str) -> type | None:
    return next(
        (
            cls
            for cls in PLUGIN_CLASSES_BY_TYPE.values()
            if cls.network_integration_type == type_ and cls.network_integration_singleton
        ),
        None,
    )


@router.get("")
async def list_all_network_settings(user: dict[str, Any] = Depends(get_current_user)):
    rows = await asyncio.to_thread(list_network_integrations)
    return [{"id": r["id"], "type": r["type"], "name": r["name"], "settings": _mask(r["settings"])} for r in rows]


@router.get("/{type}")
async def get_network_settings(type: str, user: dict[str, Any] = Depends(get_current_user)):
    if type == "container":
        rows = await asyncio.to_thread(list_network_integrations, "container")
        return [{"id": r["id"], "type": r["type"], "name": r["name"], "settings": _mask(r["settings"])} for r in rows]

    row = await asyncio.to_thread(get_network_integration, type)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown network integration type '{type}'")
    return {"id": row["id"], "type": row["type"], "name": row["name"], "settings": _mask(row["settings"])}


@router.patch("/{type}")
async def update_network_settings(
    type: str, payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)
):
    if type == "container":
        raise HTTPException(status_code=400, detail="Use /api/network-settings/container/{id} to edit a named host")

    plugin_cls = _singleton_plugin_cls(type)
    if plugin_cls is None:
        raise HTTPException(status_code=404, detail=f"Unknown network integration type '{type}'")

    existing = await asyncio.to_thread(get_network_integration, type)
    base = existing["settings"] if existing else dict(plugin_cls.network_default_settings)
    merged = {**base, **payload}
    await asyncio.to_thread(save_network_integration, type, type, plugin_cls.name, merged)
    _invalidate(apply_network_integration_update(type, type, merged), type)
    return {"id": type, "type": type, "name": plugin_cls.name, "settings": _mask(merged)}


@router.post("/{type}/test-connection")
async def test_network_settings_connection(
    type: str, payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)
):
    if type == "container":
        raise HTTPException(status_code=400, detail="Use /api/network-settings/container/{id}/test-connection")
    if type == "hdhomerun":
        raise HTTPException(
            status_code=400,
            detail="Use /api/network-settings/hdhomerun/test-tuner-connection or .../test-dvr-connection",
        )
    client_fn = _TEST_CONNECTION_DISPATCH.get(type)
    if client_fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown network integration type '{type}'")

    existing = await asyncio.to_thread(get_network_integration, type)
    candidate = {**(existing["settings"] if existing else {}), **payload}
    try:
        detail = await client_fn(candidate, type)
    except _TEST_CONNECTION_ERRORS as exc:
        return {"ok": False, "detail": None, "error": str(exc)}
    return {"ok": True, "detail": detail, "error": None}


@router.post("/hdhomerun/test-tuner-connection")
async def test_hdhomerun_tuner_connection(payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)):
    existing = await asyncio.to_thread(get_network_integration, "hdhomerun")
    candidate = {**(existing["settings"] if existing else {}), **payload}
    try:
        name = await hdhomerun_client.test_tuner_connection(candidate)
    except hdhomerun_client.HDHomeRunError as exc:
        return {"ok": False, "detail": None, "error": str(exc)}
    return {"ok": True, "detail": name, "error": None}


@router.post("/hdhomerun/test-dvr-connection")
async def test_hdhomerun_dvr_connection(payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)):
    existing = await asyncio.to_thread(get_network_integration, "hdhomerun")
    candidate = {**(existing["settings"] if existing else {}), **payload}
    try:
        name = await hdhomerun_client.test_dvr_connection(candidate)
    except hdhomerun_client.HDHomeRunError as exc:
        return {"ok": False, "detail": None, "error": str(exc)}
    return {"ok": True, "detail": name, "error": None}


@router.post("/container")
async def create_container_integration(payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    settings = {**ContainerPlugin.network_default_settings, **{k: v for k, v in payload.items() if k != "name"}}
    integration_id = f"container-{uuid4().hex[:8]}"
    await asyncio.to_thread(save_network_integration, integration_id, "container", name, settings)
    return {"id": integration_id, "type": "container", "name": name, "settings": _mask(settings)}


@router.patch("/container/{id}")
async def update_container_integration(
    id: str, payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)
):
    existing = await asyncio.to_thread(get_network_integration, id)
    if existing is None or existing["type"] != "container":
        raise HTTPException(status_code=404, detail=f"Unknown container host '{id}'")
    name = payload.get("name", existing["name"])
    settings = {**existing["settings"], **{k: v for k, v in payload.items() if k != "name"}}
    await asyncio.to_thread(save_network_integration, id, "container", name, settings)
    _invalidate(apply_network_integration_update("container", id, settings), id)
    return {"id": id, "type": "container", "name": name, "settings": _mask(settings)}


@router.delete("/container/{id}")
async def delete_container_integration(id: str, admin: dict[str, Any] = Depends(get_current_admin)):
    existing = await asyncio.to_thread(get_network_integration, id)
    if existing is None or existing["type"] != "container":
        raise HTTPException(status_code=404, detail=f"Unknown container host '{id}'")
    referencing = [
        plugin.id
        for plugin in registry.all()
        if isinstance(plugin, ContainerPlugin) and plugin.config["settings"].get("network_integration_id") == id
    ]
    if referencing:
        raise HTTPException(status_code=409, detail=f"Still in use by widget(s): {', '.join(referencing)}")
    await asyncio.to_thread(delete_network_integration, id)
    return {"status": "ok"}


@router.post("/container/{id}/test-connection")
async def test_container_integration_connection(
    id: str, payload: dict[str, Any], admin: dict[str, Any] = Depends(get_current_admin)
):
    existing = await asyncio.to_thread(get_network_integration, id)
    if existing is None or existing["type"] != "container":
        raise HTTPException(status_code=404, detail=f"Unknown container host '{id}'")
    candidate = {**existing["settings"], **payload}
    try:
        detail = await container_client.test_connection(candidate)
    except container_client.ContainerError as exc:
        return {"ok": False, "detail": None, "error": str(exc)}
    return {"ok": True, "detail": detail, "error": None}
