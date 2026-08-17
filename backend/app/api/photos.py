"""Serves photos for the Photos plugin, from a local directory, a public
iCloud Shared Album, or the private iCloud Photos library.

A dedicated route rather than folding into `widgets.py`, since it streams
bytes (or redirects to a CDN URL) rather than JSON, and needs the widget's
`settings` to resolve a safe on-disk path, a fresh CDN URL, or an
authenticated download. Settings are read from the *live* registered plugin
instance (not `app.config.widget_config`, which only reflects
`dashboard.yaml` and misses DB-persisted overrides) so a directory/token/key
just saved from the widget's detail view works immediately — same reasoning
as `app/api/jellyfin.py` and `app/api/pihole.py`.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse

from app.auth import get_current_user
from app.integrations import icloud_photos, icloud_shared_album, immich_client
from app.plugins.base import registry
from app.plugins.photos.plugin import IMAGE_EXTENSIONS, PhotosPlugin
from app.storage import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/photos", tags=["photos"], dependencies=[Depends(get_current_user)])


def _get_plugin(widget_id: str) -> PhotosPlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, PhotosPlugin):
        raise HTTPException(status_code=404, detail=f"Unknown photos widget '{widget_id}'")
    return plugin


@router.get("/{widget_id}/{filename:path}")
async def get_photo(widget_id: str, filename: str, user: dict = Depends(get_current_user)):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    provider = settings.get("provider")
    if provider == "icloud_shared":
        return await _get_icloud_photo(settings, filename)
    if provider == "icloud_private":
        return await _get_icloud_private_photo(user["id"], settings, filename)
    if provider == "immich":
        return await _get_immich_photo(settings, filename)
    return _get_local_photo(settings, filename)


def _get_local_photo(settings: dict, filename: str) -> FileResponse:
    directory = Path(settings["directory"]).expanduser().resolve()
    candidate = (directory / filename).resolve()
    # `is_relative_to` allows nested subdirectory paths (for recursive
    # listings) while still rejecting any `..` traversal outside `directory`,
    # regardless of how `filename` was encoded.
    if (
        not candidate.is_relative_to(directory)
        or candidate.suffix.lower() not in IMAGE_EXTENSIONS
        or not candidate.is_file()
    ):
        raise HTTPException(status_code=404, detail="Photo not found")

    return FileResponse(candidate)


async def _get_icloud_photo(settings: dict, guid: str) -> RedirectResponse:
    raw_token = settings.get("album_token")
    if not raw_token:
        raise HTTPException(status_code=404, detail="Photo not found")
    token = icloud_shared_album.parse_token(raw_token)

    try:
        photos = await icloud_shared_album.fetch_photos(token)
    except Exception:
        logger.warning("Failed to fetch iCloud shared album photos", exc_info=True)
        raise HTTPException(status_code=404, detail="Photo not found") from None

    photo = next((p for p in photos if p["guid"] == guid), None)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    try:
        asset_url = await icloud_shared_album.fetch_asset_url(token, guid, photo["checksum"])
    except Exception:
        logger.warning("Failed to fetch iCloud shared album asset URL", exc_info=True)
        raise HTTPException(status_code=404, detail="Photo not found") from None

    if asset_url is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    return RedirectResponse(asset_url, status_code=307)


async def _get_icloud_private_photo(user_id: str, settings: dict, photo_id: str) -> Response:
    # photo_id came from the requesting viewer's own photo_index rows (see
    # PhotosPlugin._photo_index_user_id), so bytes are fetched with that same
    # user's credentials — each household member's private library is fully
    # independent.
    creds = await asyncio.to_thread(db.get_user_credentials, user_id, "icloud") or {}
    username, password = creds.get("username"), creds.get("password")
    if not icloud_photos.is_configured(username, password):
        raise HTTPException(status_code=404, detail="Photo not found")

    album_name = settings.get("album_name", "All Photos")
    # Private-library asset URLs require the authenticated session's cookies,
    # unlike the Shared Album's public CDN links, so bytes must be proxied
    # through the backend rather than redirected to.
    try:
        result = await icloud_photos.fetch_photo_bytes(user_id, username, password, photo_id, album_name)
    except Exception:
        logger.warning("Failed to fetch iCloud private photo '%s' for user '%s'", photo_id, user_id, exc_info=True)
        raise HTTPException(status_code=404, detail="Photo not found") from None

    if result is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    content, content_type = result
    return Response(content=content, media_type=content_type)


async def _get_immich_photo(settings: dict, asset_id: str) -> Response:
    if not immich_client.is_configured(settings):
        raise HTTPException(status_code=404, detail="Photo not found")

    base_url = immich_client.normalize_base_url(settings["base_url"])
    # Immich's asset endpoints require the x-api-key header, which the
    # browser won't send to a redirect target, so bytes are proxied through
    # the backend rather than redirected to (same as icloud_private).
    try:
        result = await immich_client.fetch_asset_bytes(base_url, settings["api_key"], asset_id)
    except immich_client.ImmichError:
        raise HTTPException(status_code=404, detail="Photo not found") from None
    if result is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    content, content_type = result
    return Response(content=content, media_type=content_type)
