from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.config import settings
from app.integrations import track17_client
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/packages", tags=["packages"], dependencies=[Depends(get_current_user)])


def _invalidate(widget_id: str, user_id: str) -> None:
    # Packages is a "personal"-scope plugin, so app.api.widgets caches its
    # summary/detail per (widget, user, locale) — see
    # app.api.widgets._cache_key_prefix. Sweeping this prefix catches every
    # locale variant for just the affected user without touching anyone
    # else's cached view of the same widget.
    cache.delete_prefix(f"summary:{widget_id}:{user_id}:")
    cache.delete_prefix(f"detail:{widget_id}:{user_id}:")


@router.post("")
async def create_package(payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    if not track17_client.is_configured({"track17_api_key": settings.track17_api_key}):
        raise HTTPException(status_code=400, detail="17Track API key is not configured")

    widget_id = payload.get("widget_id", "packages")
    tracking_number = payload["tracking_number"]
    try:
        await track17_client.register(settings.track17_api_key or "", tracking_number)
    except track17_client.Track17Error as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    package = await asyncio.to_thread(db.add_package, widget_id, user["id"], tracking_number, payload.get("label"))
    _invalidate(widget_id, user["id"])
    return package


@router.delete("/{package_id}")
async def remove_package(package_id: int, user: dict[str, Any] = Depends(get_current_user)):
    existing = await asyncio.to_thread(db.get_package, package_id)
    if existing is None or existing["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail=f"Unknown package '{package_id}'")
    package = await asyncio.to_thread(db.remove_package, package_id)
    _invalidate(package["widget_id"], user["id"])
    return {"status": "ok"}
