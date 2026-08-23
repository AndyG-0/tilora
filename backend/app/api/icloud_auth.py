"""Connect flow for the private iCloud Photos provider (full account access
via `icloud_photos.py`), as opposed to the icloud_shared provider, which
needs no connect step at all.

Apple ID + password are a personal credential (see `CONTRIBUTING.md`'s
settings tiers) stored per-user in `app.storage.db.user_credentials`, not a
household-wide app setting — each family member connects their own Apple ID
and gets their own 2FA session.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.integrations import icloud_photos
from app.plugins.base import registry
from app.plugins.photos.plugin import PhotosPlugin
from app.scheduler import schedule_immediate_user_photo_index
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/icloud", tags=["icloud"], dependencies=[Depends(get_current_user)])


async def _credentials(user_id: str) -> tuple[str, str]:
    creds = await asyncio.to_thread(db.get_user_credentials, user_id, "icloud") or {}
    username, password = creds.get("username"), creds.get("password")
    if not icloud_photos.is_configured(username, password):
        raise HTTPException(status_code=400, detail="iCloud username/password are not configured")
    return username, password


def _invalidate_photo_widgets(user_id: str) -> None:
    """PhotosPlugin is personal-scope and per-instance (multiple photo
    widgets can exist), so the cache key carries both the widget id and
    user_id — a bare `cache.delete("summary:photos")` never matches any
    actual stored key. Sweep every photo widget instance for this user."""
    for plugin in registry.all():
        if isinstance(plugin, PhotosPlugin):
            cache.delete_prefix(f"summary:{plugin.id}:{user_id}:")
            cache.delete_prefix(f"detail:{plugin.id}:{user_id}:")


def _reindex_private_photo_widgets(user_id: str) -> None:
    """Schedules an immediate scan of user_id's own private library for every
    icloud_private widget, right after they connect/verify — each household
    member's library is indexed independently (see PhotosPlugin), so this
    only ever touches user_id's own photo_index rows.
    """
    for plugin in registry.all():
        if isinstance(plugin, PhotosPlugin) and plugin.provider == "icloud_private":
            schedule_immediate_user_photo_index(plugin, user_id)


@router.post("/auth/start")
async def start_auth(user: dict[str, Any] = Depends(get_current_user)):
    username, password = await _credentials(user["id"])
    result = await icloud_photos.start_auth(user["id"], username, password)
    if result["connected"]:
        _invalidate_photo_widgets(user["id"])
        _reindex_private_photo_widgets(user["id"])
    return result


@router.post("/auth/verify")
async def verify_auth(payload: dict[str, str], user: dict[str, Any] = Depends(get_current_user)):
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code is required")

    verified = await icloud_photos.verify_2fa(user["id"], code)
    if verified:
        _invalidate_photo_widgets(user["id"])
        _reindex_private_photo_widgets(user["id"])
    return {"connected": verified}


@router.get("/status")
async def status(user: dict[str, Any] = Depends(get_current_user)):
    return {"connected": icloud_photos.is_connected_cached(user["id"])}


@router.get("/credentials")
async def get_credentials(user: dict[str, Any] = Depends(get_current_user)):
    creds = await asyncio.to_thread(db.get_user_credentials, user["id"], "icloud") or {}
    return {"username": creds.get("username") or "", "has_password": bool(creds.get("password"))}


@router.put("/credentials")
async def set_credentials(payload: dict[str, str], user: dict[str, Any] = Depends(get_current_user)):
    # A blank password means "keep the current one" — the client never has
    # the plaintext to resend (it's write-only), so an update that only
    # touches the username would otherwise 400 against an already-connected
    # account.
    existing = await asyncio.to_thread(db.get_user_credentials, user["id"], "icloud") or {}
    username = payload.get("username") or existing.get("username")
    password = payload.get("password") or existing.get("password")
    if not icloud_photos.is_configured(username, password):
        raise HTTPException(status_code=400, detail="username and password are required")
    credentials = {"username": username, "password": password}
    await asyncio.to_thread(db.save_user_credentials, user["id"], "icloud", credentials)
    icloud_photos.invalidate_service_cache(user["id"], clear_disk=True)
    _invalidate_photo_widgets(user["id"])
    return {"username": username, "has_password": bool(password)}


@router.delete("/credentials")
async def clear_credentials(user: dict[str, Any] = Depends(get_current_user)):
    await asyncio.to_thread(db.delete_user_credentials, user["id"], "icloud")
    icloud_photos.invalidate_service_cache(user["id"], clear_disk=True)
    _invalidate_photo_widgets(user["id"])
    return {"status": "ok"}
