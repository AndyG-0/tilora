"""NASA APOD (Astronomy Picture of the Day) HTTP client (api.nasa.gov).

Falls back to NASA's shared "DEMO_KEY" when no key is configured, so the
plugin works with zero setup — the only cost is DEMO_KEY's much lower
shared rate limit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.nasa.gov/planetary/apod"
_TIMEOUT_SECONDS = 15
_DEFAULT_KEY = "DEMO_KEY"

# One retry is enough to smooth over the transient blips (a dropped
# connection, a momentary 5xx, a 429 from DEMO_KEY's shared rate limit) that
# make this widget look "often unavailable" in practice — anything that
# fails twice in a row is unlikely to be fixed by a third try.
_MAX_ATTEMPTS = 2
_RETRY_BACKOFF_SECONDS = 0.5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class NASAError(Exception):
    """Raised when the NASA APOD API can't be reached or rejects a request."""


async def get_apod(api_key: str | None, date: str | None = None) -> dict[str, Any]:
    """Fetch the Astronomy Picture of the Day for `date` (defaults to today).

    Always requests `thumbs=true` so video-`media_type` days (some APODs are
    a YouTube embed, not an image) still come back with a `thumbnail_url`
    usable for the tile/summary view.
    """
    params: dict[str, str] = {"api_key": api_key or _DEFAULT_KEY, "thumbs": "true"}
    if date is not None:
        params["date"] = date

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == _MAX_ATTEMPTS
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.get(_BASE_URL, params=params)
        except httpx.HTTPError as exc:
            if is_last_attempt:
                raise NASAError(f"Could not reach NASA APOD API: {exc}") from exc
            logger.debug("NASA APOD request failed (%s), retrying", exc)
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code in _RETRYABLE_STATUS_CODES and not is_last_attempt:
            logger.debug("NASA APOD API returned HTTP %s, retrying", response.status_code)
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue
        break

    try:
        body = response.json()
    except ValueError as exc:
        raise NASAError("NASA APOD API returned a non-JSON response") from exc

    if response.status_code >= 400:
        message = body.get("msg") or body.get("error", {}).get("message") or f"HTTP {response.status_code}"
        raise NASAError(f"NASA APOD API error: {message}")

    return {
        "title": body.get("title"),
        "explanation": body.get("explanation"),
        "url": body.get("url"),
        "hdurl": body.get("hdurl"),
        "thumbnail_url": body.get("thumbnail_url"),
        "media_type": body.get("media_type"),
        "date": body.get("date"),
        "copyright": body.get("copyright"),
    }
