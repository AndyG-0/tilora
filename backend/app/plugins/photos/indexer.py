"""Background population of the `photo_index`/`photo_index_meta` tables
(app.storage.db) that `PhotosPlugin.get_summary`/`get_detail` read from.

Enumerating a photo source (a full folder walk, an iCloud Shared Album
fetch, a paginated private-library scan) is comparatively slow, so it
happens here — off the request path, on an interval scheduled by
app.scheduler — rather than per request.
"""

from __future__ import annotations

import asyncio
import logging

from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db

logger = logging.getLogger(__name__)


async def index_photos(plugin: PhotosPlugin) -> None:
    """Runs one full enumeration of `plugin`'s photo source and (re)writes
    its photo_index rows. Swallows all exceptions so a bad scan (network
    error, missing directory, expired iCloud session) leaves the previous
    index in place instead of crashing the scheduler or wiping good data.
    """
    generation = db.begin_photo_index_scan(plugin.id)
    position = 0
    try:
        async for chunk in plugin._enumerate_photo_ids_chunks():
            if not chunk:
                continue
            await asyncio.to_thread(db.upsert_photo_index_chunk, plugin.id, generation, chunk, position)
            position += len(chunk)
        await asyncio.to_thread(db.finish_photo_index_scan, plugin.id, generation)
        logger.info("Indexed %d photos for widget '%s'", position, plugin.id)
    except Exception as exc:
        logger.exception("Failed to index photos for widget '%s'", plugin.id)
        await asyncio.to_thread(db.mark_photo_index_scan_failed, plugin.id, str(exc))
