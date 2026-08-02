"""Serves photos for the Photos plugin, from a local directory, a public
iCloud Shared Album, or the private iCloud Photos library.

A dedicated route rather than folding into `widgets.py`, since it streams
bytes (or redirects to a CDN URL) rather than JSON, and needs the widget's
`settings` to resolve a safe on-disk path, a fresh CDN URL, or an
authenticated download.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse

from app.auth import get_current_user
from app.config import effective_settings, widget_config
from app.integrations import icloud_photos, icloud_shared_album, immich_client
from app.plugins.photos.plugin import IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/photos", tags=["photos"], dependencies=[Depends(get_current_user)])


@router.get("/{widget_id}/{filename:path}")
async def get_photo(widget_id: str, filename: str):
    try:
        widget = widget_config(widget_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown widget '{widget_id}'") from None
    if widget["type"] != "photos":
        raise HTTPException(status_code=404, detail=f"Widget '{widget_id}' is not a photos widget")

    settings = widget["settings"]
    provider = settings.get("provider")
    if provider == "icloud_shared":
        return await _get_icloud_photo(settings, filename)
    if provider == "icloud_private":
        return await _get_icloud_private_photo(settings, filename)
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

    photos = await icloud_shared_album.fetch_photos(token)
    photo = next((p for p in photos if p["guid"] == guid), None)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    asset_url = await icloud_shared_album.fetch_asset_url(token, guid, photo["checksum"])
    if asset_url is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    return RedirectResponse(asset_url, status_code=307)


async def _get_icloud_private_photo(settings: dict, photo_id: str) -> Response:
    creds = effective_settings()
    username, password = creds.get("icloud_username"), creds.get("icloud_password")
    if not icloud_photos.is_configured(username, password):
        raise HTTPException(status_code=404, detail="Photo not found")

    album_name = settings.get("album_name", "All Photos")
    # Private-library asset URLs require the authenticated session's cookies,
    # unlike the Shared Album's public CDN links, so bytes must be proxied
    # through the backend rather than redirected to.
    result = await icloud_photos.fetch_photo_bytes(username, password, photo_id, album_name)
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
