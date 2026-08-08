"""NASA APOD (Astronomy Picture of the Day) HTTP client (api.nasa.gov).

Falls back to NASA's shared "DEMO_KEY" when no key is configured, so the
plugin works with zero setup — the only cost is DEMO_KEY's much lower
shared rate limit.
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE_URL = "https://api.nasa.gov/planetary/apod"
_TIMEOUT_SECONDS = 15
_DEFAULT_KEY = "DEMO_KEY"


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

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(_BASE_URL, params=params)
    except httpx.HTTPError as exc:
        raise NASAError(f"Could not reach NASA APOD API: {exc}") from exc

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
