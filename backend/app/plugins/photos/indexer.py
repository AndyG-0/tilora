"""Background population of the `photo_index`/`photo_index_meta` tables
(app.storage.db) that `PhotosPlugin.get_summary`/`get_detail` read from.

Enumerating a photo source (a full folder walk, an iCloud Shared Album
fetch, a paginated private-library scan) is comparatively slow, so it
happens here — off the request path, on an interval scheduled by
app.scheduler — rather than per request.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db

logger = logging.getLogger(__name__)


async def index_photos(plugin: PhotosPlugin) -> None:
    """Runs one full enumeration of `plugin`'s photo source and (re)writes
    its photo_index rows.

    For icloud_private, each connected household member has their own
    private library (see PhotosPlugin._photo_index_user_id), so a `plugin`
    with no `requesting_user_id` set — the registry singleton the scheduler
    always passes in — fans out into one scan per user with saved iCloud
    credentials, each against its own `with_settings(user_id=...)` clone,
    rather than a single shared scan. Every other provider, and any
    icloud_private plugin already scoped to a specific user (the immediate
    reindex triggered right after that user connects, see
    app.api.icloud_auth), just runs the one scan directly.
    """
    if plugin.provider == "icloud_private" and plugin.requesting_user_id is None:
        user_ids = await asyncio.to_thread(db.list_user_ids_with_credentials, "icloud")
        for user_id in user_ids:
            await _run_scan(plugin.with_settings(user_id=user_id))
        return
    await _run_scan(plugin)


async def _run_scan(plugin: PhotosPlugin) -> None:
    """Runs one full enumeration for a single (widget, user) pair. Swallows
    all exceptions so a bad scan (network error, missing directory, expired
    iCloud session) leaves the previous index in place instead of crashing
    the scheduler or wiping good data.
    """
    user_id = plugin._photo_index_user_id
    generation = db.begin_photo_index_scan(plugin.id, user_id)
    position = 0
    try:
        # aclosing() ensures the enumeration generator (and, transitively,
        # any generator it wraps — e.g. icloud_photos.iter_photo_chunks) is
        # promptly, deterministically closed if this loop body raises
        # (e.g. a `database is locked` error from upsert_photo_index_chunk),
        # instead of being silently dropped and left to async-generator GC
        # finalization at some later, unpredictable time.
        async with contextlib.aclosing(plugin._enumerate_photo_ids_chunks()) as chunks:
            async for chunk in chunks:
                if not chunk:
                    continue
                await asyncio.to_thread(db.upsert_photo_index_chunk, plugin.id, generation, chunk, position, user_id)
                position += len(chunk)
        await asyncio.to_thread(db.finish_photo_index_scan, plugin.id, generation, user_id)
        logger.info("Indexed %d photos for widget '%s' (user=%s)", position, plugin.id, user_id or "shared")
    except Exception as exc:
        logger.exception("Failed to index photos for widget '%s' (user=%s)", plugin.id, user_id or "shared")
        await asyncio.to_thread(db.mark_photo_index_scan_failed, plugin.id, str(exc), user_id)
