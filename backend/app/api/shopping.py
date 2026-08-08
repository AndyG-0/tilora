from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/shopping", tags=["shopping"], dependencies=[Depends(get_current_user)])


def _invalidate(widget_id: str) -> None:
    # Shopping is a "network"-scope plugin shared by the whole household, so
    # app.api.widgets caches its summary/detail per (widget, locale) only —
    # see app.api.widgets._cache_key_prefix. Sweeping this prefix catches
    # every locale variant without needing to know which one is cached.
    cache.delete_prefix(f"summary:{widget_id}:")
    cache.delete_prefix(f"detail:{widget_id}:")


@router.post("")
async def create_item(payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    widget_id = payload.get("widget_id", "shopping")
    item = await asyncio.to_thread(db.add_shopping_item, widget_id, payload["text"], user["name"])
    _invalidate(widget_id)
    return item


@router.post("/{item_id}/check")
async def check_item(item_id: int, user: dict[str, Any] = Depends(get_current_user)):
    item = await asyncio.to_thread(db.check_shopping_item, item_id, user["name"])
    if item is None:
        raise HTTPException(status_code=404, detail=f"Unknown shopping item '{item_id}'")
    _invalidate(item["widget_id"])
    return item


@router.delete("/{item_id}")
async def remove_item(item_id: int):
    item = await asyncio.to_thread(db.remove_shopping_item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Unknown shopping item '{item_id}'")
    _invalidate(item["widget_id"])
    return {"status": "ok"}
