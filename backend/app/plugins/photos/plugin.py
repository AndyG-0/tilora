"""Photos plugin: slideshow widget backed by a local image folder, a public
iCloud Shared Album, or the private iCloud Photos library.

`settings.provider` picks which:
- "local" (default): reads `settings.directory`, a path on the machine
  running the backend.
- "icloud_shared": reads `settings.album_token` (a share link like
  `https://www.icloud.com/sharedalbum/#B0z5qAGN1JIFd3y`, or the bare token)
  via `app.integrations.icloud_shared_album` — no Apple ID required, since
  it's Apple's own public "Public Website" sharing feature, but anyone with
  the link can view it.
- "icloud_private": full account access to a named album (default
  "All Photos") via `app.integrations.icloud_photos`, gated by real Apple ID
  + 2FA (connected from Settings + this widget's detail view) — private, but
  needs credentials stored server-side and periodic (~2 month) reconnects.
- "immich": one album on a self-hosted Immich (https://immich.app) server,
  via `app.integrations.immich_client`. Reads `settings.base_url`,
  `settings.api_key`, and `settings.album_id` — like icloud_shared, exactly
  one album/source, no "browse the whole library" support (that would need
  pagination/search UI this plugin doesn't have).

Other cloud providers (Google Photos, WebDAV, etc.) remain unsupported — see
TODO.md.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.config import effective_settings
from app.integrations import icloud_photos, icloud_shared_album, immich_client
from app.plugins.base import Plugin
from app.storage import db

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_DEFAULT_PRIVATE_ALBUM = "All Photos"


def _scan_local_photos_recursive(directory: Path) -> list[str]:
    ids = []
    for dirpath, _dirnames, filenames in directory.walk(on_error=lambda e: None):
        for name in filenames:
            candidate = dirpath / name
            if candidate.suffix.lower() in IMAGE_EXTENSIONS:
                ids.append(candidate.relative_to(directory).as_posix())
    return sorted(ids)


class PhotosPlugin(Plugin):
    id = "photos"
    name = "Photos"
    refresh_interval_seconds = 60
    default_settings = {"provider": "local"}

    @property
    def provider(self) -> str:
        return self.config["settings"].get("provider", "local")

    @property
    def directory(self) -> Path | None:
        directory = self.config["settings"].get("directory")
        return Path(directory).expanduser() if directory else None

    @property
    def album_token(self) -> str | None:
        raw = self.config["settings"].get("album_token")
        return icloud_shared_album.parse_token(raw) if raw else None

    @property
    def album_name(self) -> str:
        return self.config["settings"].get("album_name", _DEFAULT_PRIVATE_ALBUM)

    @property
    def immich_base_url(self) -> str | None:
        raw = self.config["settings"].get("base_url")
        return immich_client.normalize_base_url(raw) if raw else None

    @property
    def immich_api_key(self) -> str | None:
        return self.config["settings"].get("api_key") or None

    @property
    def immich_album_id(self) -> str | None:
        return self.config["settings"].get("album_id") or None

    @property
    def interval_seconds(self) -> int:
        return int(self.config["settings"].get("interval_seconds", 30))

    @property
    def recursive(self) -> bool:
        return bool(self.config["settings"].get("recursive", False))

    @property
    def index_refresh_seconds(self) -> int:
        # Floored at 60s so a misconfigured 0/negative value can't break
        # APScheduler's IntervalTrigger or hammer the source.
        return max(60, int(self.config["settings"].get("index_refresh_seconds", 3600)))

    async def _local_photo_ids(self) -> list[str]:
        directory = self.directory
        if directory is None or not directory.is_dir():
            return []
        if not self.recursive:
            return sorted(p.name for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        return await asyncio.to_thread(_scan_local_photos_recursive, directory)

    async def _shared_photo_ids(self) -> list[str]:
        if self.album_token is None:
            return []
        photos = await icloud_shared_album.fetch_photos(self.album_token)
        return [photo["guid"] for photo in photos]

    async def _photo_ids(self) -> list[str]:
        """Cheap read from the persisted index — never re-enumerates the
        live source. The index is populated out-of-band by the background
        job (app.plugins.photos.indexer.index_photos, scheduled from
        app.scheduler) via `_enumerate_photo_ids_chunks` below.
        """
        return await asyncio.to_thread(db.photo_index_photo_ids, self.id)

    async def _enumerate_photo_ids_chunks(self) -> AsyncIterator[list[str]]:
        """The slow, full-source enumeration — local FS walk, one iCloud
        Shared Album webstream call, paginated iCloud private-library fetch,
        or paginated Immich album search. Only ever called by the background
        index job, never by get_summary/get_detail (which read the
        persisted index instead).
        """
        if self.provider == "icloud_shared":
            ids = await self._shared_photo_ids()
            if ids:
                yield ids
            return
        if self.provider == "icloud_private":
            creds = effective_settings()
            username, password = creds.get("icloud_username"), creds.get("icloud_password")
            if not icloud_photos.is_configured(username, password):
                return
            async for chunk in icloud_photos.iter_photo_chunks(username, password, self.album_name):
                yield [photo["id"] for photo in chunk]
            return
        if self.provider == "immich":
            settings = self.config["settings"]
            if not immich_client.is_configured(settings):
                return
            async for chunk in immich_client.iter_album_asset_chunks(
                self.immich_base_url, self.immich_api_key, self.immich_album_id
            ):
                yield [asset["id"] for asset in chunk]
            return
        ids = await self._local_photo_ids()
        if ids:
            yield ids

    def _photo(self, photo_id: str) -> dict[str, str]:
        return {"filename": photo_id, "url": f"/api/photos/{self.id}/{photo_id}"}

    async def _index_status_fields(self, photo_ids: list[str]) -> dict[str, Any]:
        """Surfaces the background indexer's state (`db.photo_index_status`)
        when it explains why `photo_ids` is empty — either the first scan
        hasn't completed yet, or it completed with an error — so the UI can
        show "Indexing…"/an error instead of a bare "No photos found".
        """
        if photo_ids:
            return {}
        status = await asyncio.to_thread(db.photo_index_status, self.id)
        if status is None:
            return {"indexing": True}
        if status["status"] == "error":
            return {"index_error": status["last_error"]}
        return {}

    async def get_summary(self) -> dict[str, Any]:
        photo_ids = await self._photo_ids()
        result: dict[str, Any] = {"count": 0, "current": None}
        if photo_ids:
            # Time-bucketed index so every client polling the summary sees
            # the same "current" photo without a shared server-side cursor.
            index = int(time.time() // self.interval_seconds) % len(photo_ids)
            result = {"count": len(photo_ids), "current": self._photo(photo_ids[index])}
        result.update(await self._index_status_fields(photo_ids))
        if self.provider == "icloud_private":
            result["connected"] = icloud_photos.is_connected_cached()
        return result

    async def get_detail(self) -> dict[str, Any]:
        photo_ids = await self._photo_ids()
        result: dict[str, Any] = {
            "provider": self.provider,
            "count": len(photo_ids),
            "interval_seconds": self.interval_seconds,
            "photos": [self._photo(photo_id) for photo_id in photo_ids],
        }
        result.update(await self._index_status_fields(photo_ids))
        if self.provider == "local":
            result["directory"] = self.config["settings"].get("directory") or None
            result["recursive"] = self.recursive
        if self.provider == "icloud_shared":
            result["album_token"] = self.config["settings"].get("album_token") or None
        if self.provider == "icloud_private":
            result["connected"] = icloud_photos.is_connected_cached()
        if self.provider == "immich":
            # api_key is write-only: only whether one is set is exposed, never
            # the raw value (same masking convention as SteamPlugin._safe_settings).
            result["immich_base_url"] = self.config["settings"].get("base_url") or None
            result["has_immich_api_key"] = bool(self.config["settings"].get("api_key"))
            result["immich_album_id"] = self.config["settings"].get("album_id") or None
        return result
