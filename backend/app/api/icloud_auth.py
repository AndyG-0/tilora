"""Connect flow for the private iCloud Photos provider (full account access
via `icloud_photos.py`), as opposed to the icloud_shared provider, which
needs no connect step at all.

Apple ID + password come from the global app settings (Settings page or
`.env`), not a per-widget setting — one Apple ID, same as CalDAV/Google
Calendar are a single connected account rather than per-widget credentials.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import effective_settings
from app.integrations import icloud_photos
from app.plugins.base import registry
from app.plugins.photos.plugin import PhotosPlugin
from app.scheduler import schedule_photo_index
from app.storage.cache import cache

router = APIRouter(prefix="/api/icloud", tags=["icloud"])


def _credentials() -> tuple[str, str]:
    creds = effective_settings()
    username, password = creds.get("icloud_username"), creds.get("icloud_password")
    if not icloud_photos.is_configured(username, password):
        raise HTTPException(status_code=400, detail="iCloud username/password are not configured")
    return username, password


def _reindex_private_photo_widgets() -> None:
    for plugin in registry.all():
        if isinstance(plugin, PhotosPlugin) and plugin.provider == "icloud_private":
            schedule_photo_index(plugin)


@router.post("/auth/start")
async def start_auth():
    username, password = _credentials()
    result = await icloud_photos.start_auth(username, password)
    if result["connected"]:
        cache.delete("summary:photos")
        cache.delete("detail:photos")
        _reindex_private_photo_widgets()
    return result


@router.post("/auth/verify")
async def verify_auth(payload: dict[str, str]):
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code is required")

    verified = await icloud_photos.verify_2fa(code)
    if verified:
        cache.delete("summary:photos")
        cache.delete("detail:photos")
        _reindex_private_photo_widgets()
    return {"connected": verified}


@router.get("/status")
async def status():
    return {"connected": icloud_photos.is_connected_cached()}
