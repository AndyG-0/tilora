from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import DEVICE_COOKIE_NAME, get_current_device, get_current_user, new_token, set_device_cookie
from app.storage.db import (
    copy_widget_layout,
    create_device,
    delete_device,
    get_device,
    has_widget_layout,
    list_devices,
    update_device,
)

router = APIRouter(prefix="/api/devices", tags=["devices"])


class RenameDeviceRequest(BaseModel):
    name: str


class CopyLayoutRequest(BaseModel):
    source_device_id: str


def _shape(device: dict[str, Any]) -> dict[str, Any]:
    return {"id": device["id"], "name": device["name"]}


@router.post("/register")
async def register_device(request: Request, response: Response):
    # Idempotent: a browser that already has a valid device cookie gets its
    # existing device back unchanged, rather than minting a new one on every
    # reload.
    existing_id = request.cookies.get(DEVICE_COOKIE_NAME)
    existing = await asyncio.to_thread(get_device, existing_id) if existing_id else None
    if existing is not None:
        set_device_cookie(response, existing["id"])
        return {**_shape(existing), "is_new": False}

    device_id = new_token()
    now = datetime.now(UTC).isoformat()
    await asyncio.to_thread(create_device, device_id, "New Device", now, now)
    set_device_cookie(response, device_id)
    return {"id": device_id, "name": "New Device", "is_new": True}


@router.get("/me")
async def current_device(device: dict[str, Any] = Depends(get_current_device)):
    return _shape(device)


@router.patch("/me")
async def rename_current_device(payload: RenameDeviceRequest, device: dict[str, Any] = Depends(get_current_device)):
    await asyncio.to_thread(update_device, device["id"], name=payload.name)
    return {"id": device["id"], "name": payload.name}


@router.get("")
async def list_all_devices(user: dict[str, Any] = Depends(get_current_user)):
    devices = await asyncio.to_thread(list_devices)
    return [{"id": d["id"], "name": d["name"], "last_seen_at": d["last_seen_at"]} for d in devices]


@router.get("/me/layout-status")
async def layout_status(
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    has_layout = await asyncio.to_thread(has_widget_layout, user["id"], device["id"])
    return {"has_layout": has_layout}


@router.post("/me/copy-layout")
async def copy_layout_to_current_device(
    payload: CopyLayoutRequest,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    if payload.source_device_id == device["id"]:
        raise HTTPException(status_code=400, detail="Source and target device must differ")
    source = await asyncio.to_thread(get_device, payload.source_device_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown device '{payload.source_device_id}'")
    await asyncio.to_thread(copy_widget_layout, user["id"], payload.source_device_id, device["id"])
    return {"status": "ok"}


@router.delete("/{device_id}")
async def forget_device(
    device_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    current_device: dict[str, Any] = Depends(get_current_device),
):
    if device_id == current_device["id"]:
        raise HTTPException(status_code=400, detail="Can't forget the device you're currently using")
    device = await asyncio.to_thread(get_device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Unknown device '{device_id}'")
    await asyncio.to_thread(delete_device, device_id)
    return {"status": "ok"}
