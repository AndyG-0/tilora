from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/chores", tags=["chores"], dependencies=[Depends(get_current_user)])


def _invalidate(widget_id: str, user_id: str) -> None:
    # Chores is a "personal"-scope plugin, so app.api.widgets caches its
    # summary/detail per (widget, user, locale) — see
    # app.api.widgets._cache_key_prefix. Sweeping this user's prefix catches
    # every locale variant without needing to know which one is cached.
    cache.delete_prefix(f"summary:{widget_id}:{user_id}:")
    cache.delete_prefix(f"detail:{widget_id}:{user_id}:")


@router.post("")
async def create_chore(payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    widget_id = payload.get("widget_id", "chores")
    chore = await asyncio.to_thread(db.add_chore, widget_id, user["id"], payload["text"])
    _invalidate(widget_id, user["id"])
    return chore


@router.post("/{chore_id}/complete")
async def complete_chore(chore_id: int, user: dict[str, Any] = Depends(get_current_user)):
    chore = await asyncio.to_thread(db.complete_chore, chore_id, user["id"])
    if chore is None:
        raise HTTPException(status_code=404, detail=f"Unknown to-do item '{chore_id}'")
    _invalidate(chore["widget_id"], user["id"])
    return chore


@router.delete("/{chore_id}")
async def remove_chore(chore_id: int, user: dict[str, Any] = Depends(get_current_user)):
    chore = await asyncio.to_thread(db.remove_chore, chore_id, user["id"])
    if chore is None:
        raise HTTPException(status_code=404, detail=f"Unknown to-do item '{chore_id}'")
    _invalidate(chore["widget_id"], user["id"])
    return {"status": "ok"}
