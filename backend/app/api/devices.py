from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import DEVICE_COOKIE_NAME, get_current_device, get_current_user, new_token, set_device_cookie
from app.storage.db import create_device, delete_device, get_device, list_devices, update_device

router = APIRouter(prefix="/api/devices", tags=["devices"])


class RenameDeviceRequest(BaseModel):
    name: str


def _shape(device: dict[str, Any]) -> dict[str, Any]:
    return {"id": device["id"], "name": device["name"]}


def _generate_unique_device_name(existing_names: Iterable[str], base: str = "New Device") -> str:
    normalized = {n.strip().casefold() for n in existing_names if n and n.strip()}
    if base.casefold() not in normalized:
        return base
    counter = 2
    while f"{base} {counter}".casefold() in normalized:
        counter += 1
    return f"{base} {counter}"


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
    all_devices = await asyncio.to_thread(list_devices)
    device_name = _generate_unique_device_name(d["name"] for d in all_devices)
    await asyncio.to_thread(create_device, device_id, device_name, now, now)
    set_device_cookie(response, device_id)
    return {"id": device_id, "name": device_name, "is_new": True}


@router.get("/me")
async def current_device(device: dict[str, Any] = Depends(get_current_device)):
    return _shape(device)


@router.patch("/me")
async def rename_current_device(payload: RenameDeviceRequest, device: dict[str, Any] = Depends(get_current_device)):
    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Device name cannot be empty")
    if len(new_name) > 40:
        raise HTTPException(status_code=400, detail="Device name must be 40 characters or fewer")

    all_devices = await asyncio.to_thread(list_devices)
    for other in all_devices:
        if other["id"] != device["id"] and other["name"].strip().casefold() == new_name.casefold():
            raise HTTPException(status_code=400, detail=f"A device named '{new_name}' already exists")

    await asyncio.to_thread(update_device, device["id"], name=new_name)
    return {"id": device["id"], "name": new_name}


@router.get("")
async def list_all_devices(user: dict[str, Any] = Depends(get_current_user)):
    devices = await asyncio.to_thread(list_devices)
    return [{"id": d["id"], "name": d["name"], "last_seen_at": d["last_seen_at"]} for d in devices]


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
