"""NASA Astronomy Picture of the Day plugin: a fun, low-maintenance kiosk
filler in the same spirit as Photos, backed by api.nasa.gov's free APOD
endpoint (works with zero configuration via the shared DEMO_KEY).
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.config import settings
from app.integrations import nasa_client
from app.plugins.base import Plugin

logger = logging.getLogger(__name__)

# APOD only updates roughly once a day — no point polling more often than
# this, it just burns DEMO_KEY's shared rate limit for households that
# haven't set nasa_api_key.
_REFRESH_INTERVAL_SECONDS = 21600  # 6 hours


class NASAApodPlugin(Plugin):
    id = "nasa_apod"
    name = "NASA Astronomy Picture of the Day"
    refresh_interval_seconds = _REFRESH_INTERVAL_SECONDS
    default_settings: ClassVar[dict[str, Any]] = {"title": "Astronomy Picture of the Day"}

    @property
    def title(self) -> str:
        return self.config["settings"].get("title", self.name)

    async def _fetch(self) -> dict[str, Any] | None:
        try:
            return await nasa_client.get_apod(settings.nasa_api_key)
        except nasa_client.NASAError as exc:
            logger.warning("Could not fetch NASA APOD for widget '%s': %s", self.id, exc)
            return None

    async def get_summary(self) -> dict[str, Any]:
        apod = await self._fetch()
        if apod is None:
            return {"title": self.title, "available": False}
        return {
            "title": self.title,
            "available": True,
            "apod_title": apod["title"],
            "date": apod["date"],
            "media_type": apod["media_type"],
            "thumbnail_url": apod["url"] if apod["media_type"] == "image" else apod["thumbnail_url"],
        }

    async def get_detail(self) -> dict[str, Any]:
        apod = await self._fetch()
        if apod is None:
            return {"title": self.title, "available": False}
        detail = {**apod, "apod_title": apod["title"]}
        del detail["title"]
        return {"title": self.title, "available": True, **detail}
