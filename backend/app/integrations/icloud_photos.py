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
import concurrent.futures
import logging
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from icloudpy import ICloudPyService
from icloudpy.exceptions import ICloudPyAPIResponseException, ICloudPyException, ICloudPyFailedLoginException

from app.config import ICLOUD_SESSION_DIR
from app.storage.cache import cache

logger = logging.getLogger(__name__)

_SERVICE_CACHE_TTL_SECONDS = 30 * 60
_PENDING_SERVICE_TTL_SECONDS = 10 * 60
_PHOTO_LIST_CACHE_TTL_SECONDS = 5 * 60
_DEFAULT_ALBUM = "All Photos"
# Bounds how long the producer thread in iter_photo_chunks will wait for the
# consumer to drain the queue before giving up and exiting on its own. If a
# consumer abandons the `async for` over this generator without it being
# aclose()'d (e.g. a DB error mid-loop in app.plugins.photos.indexer._run_scan),
# nobody calls queue.get() again — without this bound, the producer thread
# blocks in run_coroutine_threadsafe(...).result() *forever*, permanently
# occupying one worker slot in asyncio's shared default ThreadPoolExecutor
# (the same pool every asyncio.to_thread(db.*) call in this app uses). 30s is
# comfortably above the ~10s worst case for a single *live* consumer
# iteration (bounded by sqlite's busy_timeout, see app.storage.db._connect)
# plus scheduling overhead, so a merely-slow-but-alive consumer never trips
# it, while a truly abandoned one is bounded to roughly this long instead of
# indefinitely.
_QUEUE_PUT_TIMEOUT_SECONDS = 30


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


def _is_auth_error(exc: Exception) -> bool:
    if isinstance(exc, ICloudPyAPIResponseException):
        return exc.code in (421, 450, 500) or "Authentication required" in str(exc)
    return False


def _format_auth_error(exc: Exception) -> str:
    msg = str(exc)
    if "503" in msg or "Service Unavailable" in msg:
        return (
            "Apple authentication server is temporarily throttling or unavailable (HTTP 503). "
            "Please wait 15–30 minutes before trying again."
        )
    if "Invalid email/password" in msg:
        return "Invalid Apple ID or password."
    return "Could not connect to Apple ID."


def _build_service(user_id: str, username: str, password: str) -> ICloudPyService:
    session_dir = _session_dir(user_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    return ICloudPyService(username, password, cookie_directory=str(session_dir))


async def _get_or_build_service(
    user_id: str, username: str, password: str
) -> tuple[ICloudPyService | None, str | None]:
    cache_key = _service_cache_key(user_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, None

    try:
        service = await asyncio.to_thread(_build_service, user_id, username, password)
    except ICloudPyFailedLoginException as exc:
        logger.warning("iCloud login failed for account '%s': %s", username, exc)
        return None, _format_auth_error(exc)
    except ICloudPyAPIResponseException as exc:
        logger.warning("iCloud API error initializing service for account '%s': %s", username, exc)
        return None, _format_auth_error(exc)
    except (ICloudPyException, Exception) as exc:
        logger.warning("iCloud service initialization failed for account '%s'", username, exc_info=True)
        return None, _format_auth_error(exc)

    if not service.requires_2fa:
        cache.set(cache_key, service, _SERVICE_CACHE_TTL_SECONDS)
    return service, None


async def start_auth(user_id: str, username: str, password: str) -> dict[str, Any]:
    """Authenticates (or resumes a trusted session); reports whether 2FA is needed."""
    try:
        service, error_msg = await _get_or_build_service(user_id, username, password)
    except Exception as exc:
        logger.warning("iCloud start_auth failed for user %s", user_id, exc_info=True)
        return {"connected": False, "requires_2fa": False, "error": _format_auth_error(exc)}

    if service is None:
        return {"connected": False, "requires_2fa": False, "error": error_msg}
    if service.requires_2fa:
        try:
            pushed = await asyncio.to_thread(service.trigger_2fa_push_notification)
            if not pushed:
                logger.warning("iCloud 2FA push notification trigger failed for account '%s'", username)
        except Exception:
            logger.warning("iCloud 2FA push notification failed for account '%s'", username, exc_info=True)
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

    try:
        verified = await asyncio.to_thread(_verify)
    except Exception:
        logger.warning("iCloud 2FA verification failed for user %s", user_id, exc_info=True)
        return False

    if verified:
        cache.delete(_pending_service_cache_key(user_id))
        cache.set(_service_cache_key(user_id), service, _SERVICE_CACHE_TTL_SECONDS)
    return verified


def clear_session_dir(user_id: str) -> None:
    session_dir = _session_dir(user_id)
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)


def invalidate_service_cache(user_id: str, clear_disk: bool = False) -> None:
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
    if clear_disk:
        clear_session_dir(user_id)


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

    service, _ = await _get_or_build_service(user_id, username, password)
    if service is None or service.requires_2fa:
        return []

    def _list() -> list[Any]:
        album = service.photos.albums.get(album_name)
        if album is None:
            return []
        return list(album.photos)

    try:
        assets = await asyncio.to_thread(_list)
    except ICloudPyAPIResponseException as exc:
        logger.warning("iCloud API error in list_photos for user %s: %s", user_id, exc)
        if _is_auth_error(exc):
            invalidate_service_cache(user_id)
        return []
    except Exception as exc:
        logger.warning("iCloud list_photos failed for user %s: %s", user_id, exc, exc_info=True)
        return []

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

    Callers MUST ensure this generator is promptly `aclose()`'d if abandoned
    before exhaustion (e.g. via `contextlib.aclosing()`), not just dropped —
    see app.plugins.photos.plugin._enumerate_photo_ids_chunks for the
    required pattern. Even so, the producer thread's queue.put() calls are
    independently bounded by `_QUEUE_PUT_TIMEOUT_SECONDS` so it can never
    block forever regardless of when (or whether) aclose() runs.
    """
    service, _ = await _get_or_build_service(user_id, username, password)
    if service is None or service.requires_2fa:
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=2)
    sentinel = object()

    def _put(item: Any) -> bool:
        """Puts `item` onto `queue` from the producer thread, bounded so a
        consumer that's gone away for good can't pin this thread (and its
        shared default-executor slot) forever. Returns False if the item
        couldn't be delivered within the timeout, in which case the caller
        should stop producing.
        """
        future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
        try:
            future.result(timeout=_QUEUE_PUT_TIMEOUT_SECONDS)
            return True
        except concurrent.futures.TimeoutError:
            # Safe from this thread: run_coroutine_threadsafe bridges `future`
            # to the underlying queue.put() Task via asyncio's internal
            # future-chaining, whose cancel-propagation already dispatches
            # through loop.call_soon_threadsafe — cancelling `future` here
            # correctly injects CancelledError into queue.put()'s await point
            # on the loop thread and unblocks it.
            future.cancel()
            logger.warning(
                "iCloud iter_photo_chunks producer for user %s timed out after %ss waiting for the "
                "consumer to drain the queue — abandoning this scan.",
                user_id,
                _QUEUE_PUT_TIMEOUT_SECONDS,
            )
            return False

    def _produce() -> None:
        try:
            album = service.photos.albums.get(album_name)
            if album is not None:
                for chunk in album.iter_chunks(chunk_size=chunk_size):
                    dicts = [_photo_dict(asset) for asset in chunk]
                    if not _put(dicts):
                        return
        except ICloudPyAPIResponseException as exc:
            logger.warning("iCloud API error in iter_photo_chunks for user %s: %s", user_id, exc)
            if _is_auth_error(exc):
                invalidate_service_cache(user_id)
        except Exception as exc:
            logger.warning("iCloud iter_photo_chunks failed for user %s: %s", user_id, exc, exc_info=True)
        finally:
            _put(sentinel)

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
        try:
            await list_photos(user_id, username, password, album_name)
        except Exception:
            logger.warning("iCloud failed listing photos during fetch_photo_bytes for user %s", user_id, exc_info=True)
        cached = cache.get(cache_key) or []

    asset = next((a for a in cached if a.id == photo_id), None)
    if asset is None:
        return None

    def _download() -> tuple[bytes, str] | None:
        response = asset.download("medium")
        if response is None:
            return None
        return response.content, response.headers.get("content-type", "image/jpeg")

    try:
        return await asyncio.to_thread(_download)
    except ICloudPyAPIResponseException as exc:
        logger.warning("iCloud API error downloading photo %s for user %s: %s", photo_id, user_id, exc)
        if _is_auth_error(exc):
            invalidate_service_cache(user_id)
        return None
    except Exception as exc:
        logger.warning("iCloud download failed for photo %s (user %s): %s", photo_id, user_id, exc, exc_info=True)
        return None
