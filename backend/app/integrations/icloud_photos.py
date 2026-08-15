"""Client for iCloud's private Photos library via the unofficial `icloudpy`
package — full account access, gated by real Apple ID authentication
(including 2FA). Contrast with `icloud_shared_album.py`, which needs no
credentials at all but only exposes one publicly-shared album.

Credentials and sessions are per-user (see `app.storage.db.user_credentials`
and PhotosPlugin's per-provider `settings_scope`) — each household member
connects their own Apple ID, so every function here takes a `user_id` used
to key both the on-disk session cookies (under
`ICLOUD_SESSION_DIR/{user_id}/`) and the in-process service/photo-list cache.

Auth is two steps, mirroring icloudpy's own flow:
1. `start_auth(user_id, username, password)` builds a session — reusing a
   previously trusted one persisted on disk when possible — and reports
   whether a 2FA code is needed.
2. If so, `verify_2fa(user_id, code)` validates it and trusts the session so
   future backend restarts don't need an interactive 2FA prompt again, until
   Apple expires that trust (currently ~2 months), at which point
   `start_auth` will report `requires_2fa: True` again and this flow must be
   repeated.

The constructed `ICloudPyService` is itself cached in-process (not just its
on-disk cookies) since building one makes a real authenticate() network
call — reused across the auth check and every photo list/download.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from icloudpy import ICloudPyService
from icloudpy.exceptions import ICloudPyFailedLoginException

from app.config import ICLOUD_SESSION_DIR
from app.storage.cache import cache

logger = logging.getLogger(__name__)

_SERVICE_CACHE_TTL_SECONDS = 30 * 60
_PENDING_SERVICE_TTL_SECONDS = 10 * 60
_PHOTO_LIST_CACHE_TTL_SECONDS = 5 * 60
_DEFAULT_ALBUM = "All Photos"


def _service_cache_key(user_id: str) -> str:
    return f"icloud_photos:service:{user_id}"


def _pending_service_cache_key(user_id: str) -> str:
    return f"icloud_photos:pending_service:{user_id}"


def _photo_list_cache_key(user_id: str) -> str:
    return f"icloud_photos:list:{user_id}"


def _session_dir(user_id: str) -> Path:
    return ICLOUD_SESSION_DIR / user_id


def is_configured(username: str | None, password: str | None) -> bool:
    return bool(username and password)


def _build_service(user_id: str, username: str, password: str) -> ICloudPyService:
    session_dir = _session_dir(user_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    return ICloudPyService(username, password, cookie_directory=str(session_dir))


async def _get_or_build_service(user_id: str, username: str, password: str) -> ICloudPyService | None:
    cache_key = _service_cache_key(user_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        service = await asyncio.to_thread(_build_service, user_id, username, password)
    except ICloudPyFailedLoginException:
        logger.warning("iCloud login failed for account '%s'", username, exc_info=True)
        return None

    if not service.requires_2fa:
        cache.set(cache_key, service, _SERVICE_CACHE_TTL_SECONDS)
    return service


async def start_auth(user_id: str, username: str, password: str) -> dict[str, Any]:
    """Authenticates (or resumes a trusted session); reports whether 2FA is needed."""
    service = await _get_or_build_service(user_id, username, password)
    if service is None:
        return {"connected": False, "requires_2fa": False}
    if service.requires_2fa:
        pushed = await asyncio.to_thread(service.trigger_2fa_push_notification)
        if not pushed:
            logger.warning("iCloud 2FA push notification trigger failed for account '%s'", username)
        cache.set(_pending_service_cache_key(user_id), service, _PENDING_SERVICE_TTL_SECONDS)
        return {"connected": False, "requires_2fa": True}
    return {"connected": True, "requires_2fa": False}


async def verify_2fa(user_id: str, code: str) -> bool:
    service = cache.get(_pending_service_cache_key(user_id))
    if service is None:
        return False

    def _verify() -> bool:
        if not service.validate_2fa_code(code):
            return False
        if not service.is_trusted_session:
            service.trust_session()
        return True

    verified = await asyncio.to_thread(_verify)
    if verified:
        cache.delete(_pending_service_cache_key(user_id))
        cache.set(_service_cache_key(user_id), service, _SERVICE_CACHE_TTL_SECONDS)
    return verified


def invalidate_service_cache(user_id: str) -> None:
    """Drops any cached authenticated service/photo-list state for a user.

    `_get_or_build_service` only rebuilds when the cache is empty, so it has
    no way to notice on its own that the user's configured Apple ID
    changed — without this, a stale session (and cached photo list) for the
    *previous* account keeps serving requests for up to
    _SERVICE_CACHE_TTL_SECONDS after the switch. Called from
    app.api.icloud_auth whenever a user's credentials are set/cleared.
    """
    cache.delete(_service_cache_key(user_id))
    cache.delete(_pending_service_cache_key(user_id))
    cache.delete(_photo_list_cache_key(user_id))


def is_connected_cached(user_id: str) -> bool:
    """Whether a trusted session is already live in-process for this user, with no network call.

    Used for a cheap status check; a full connectivity check happens
    implicitly the next time `list_photos` runs.
    """
    return cache.get(_service_cache_key(user_id)) is not None


def _photo_dict(asset: Any) -> dict[str, Any]:
    return {"id": asset.id, "filename": asset.filename}


async def list_photos(
    user_id: str, username: str, password: str, album_name: str = _DEFAULT_ALBUM
) -> list[dict[str, Any]]:
    """Metadata for photos in the given album. Cached briefly (see module docstring)."""
    cache_key = _photo_list_cache_key(user_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return [_photo_dict(asset) for asset in cached]

    service = await _get_or_build_service(user_id, username, password)
    if service is None or service.requires_2fa:
        return []

    def _list() -> list[Any]:
        album = service.photos.albums.get(album_name)
        if album is None:
            return []
        return list(album.photos)

    assets = await asyncio.to_thread(_list)
    cache.set(cache_key, assets, _PHOTO_LIST_CACHE_TTL_SECONDS)
    return [_photo_dict(asset) for asset in assets]


async def iter_photo_chunks(
    user_id: str, username: str, password: str, album_name: str = _DEFAULT_ALBUM, chunk_size: int = 200
) -> AsyncIterator[list[dict[str, Any]]]:
    """Metadata for photos in the given album, yielded in bounded-memory
    batches — for the background index scan (see app.plugins.photos.indexer),
    which can't afford `list_photos`'s `list(album.photos)` eagerly holding
    every asset (and Apple's paginated fetches behind it) in memory at once
    for a large library.

    Wraps icloudpy's blocking `PhotoAlbum.iter_chunks` generator (which
    performs blocking HTTP as it's pulled) via a producer thread feeding a
    small bounded queue, so at most a couple of chunks are ever in memory
    regardless of album size.
    """
    service = await _get_or_build_service(user_id, username, password)
    if service is None or service.requires_2fa:
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=2)
    sentinel = object()

    def _produce() -> None:
        try:
            album = service.photos.albums.get(album_name)
            if album is not None:
                for chunk in album.iter_chunks(chunk_size=chunk_size):
                    dicts = [_photo_dict(asset) for asset in chunk]
                    asyncio.run_coroutine_threadsafe(queue.put(dicts), loop).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop).result()

    producer = asyncio.create_task(asyncio.to_thread(_produce))
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            yield item
    finally:
        await producer


async def fetch_photo_bytes(
    user_id: str, username: str, password: str, photo_id: str, album_name: str = _DEFAULT_ALBUM
) -> tuple[bytes, str] | None:
    """The raw bytes + content-type for one photo, by id from `list_photos`."""
    cache_key = _photo_list_cache_key(user_id)
    cached = cache.get(cache_key)
    if cached is None:
        await list_photos(user_id, username, password, album_name)
        cached = cache.get(cache_key) or []

    asset = next((a for a in cached if a.id == photo_id), None)
    if asset is None:
        return None

    def _download() -> tuple[bytes, str] | None:
        response = asset.download("medium")
        if response is None:
            return None
        return response.content, response.headers.get("content-type", "image/jpeg")

    return await asyncio.to_thread(_download)
