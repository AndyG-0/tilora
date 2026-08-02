"""Client for Apple's iCloud Shared Album "public website" feature.

There's no official API, but the public share link (Photos app -> album ->
Share Link -> "Public Website", `https://www.icloud.com/sharedalbum/#TOKEN`)
is backed by an unauthenticated JSON API that's been stable for years:

1. POST .../sharedstreams/webstream with the token -> photo metadata
   (guids + per-size derivatives). The response may carry an
   `X-Apple-MMe-Host` header pointing at a different partition host; when
   present, the same request must be retried against that host.
2. POST .../sharedstreams/webasseturls with a list of guids -> direct CDN
   download URLs. These URLs expire after roughly an hour, so callers must
   fetch them fresh rather than persisting them.

No Apple ID or password involved, which is what makes this workable for an
unattended kiosk (contrast with `pyicloud`-style full-library access, which
needs interactive 2FA and session cookies that expire every ~2 months).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.storage.cache import cache

_DEFAULT_HOST = "p23-sharedstreams.icloud.com"
_HOST_CACHE_TTL_SECONDS = 60 * 60 * 24
_ASSET_URL_CACHE_TTL_SECONDS = 45 * 60
_PHOTO_LIST_CACHE_TTL_SECONDS = 5 * 60


def parse_token(share_url_or_token: str) -> str:
    """Accepts either a full share URL or a bare token; returns the token."""
    value = share_url_or_token.strip()
    if "#" in value:
        value = value.rsplit("#", 1)[1]
    return value


def is_configured(album_token: str | None) -> bool:
    return bool(album_token)


def _largest_derivative(photo: dict[str, Any]) -> dict[str, Any] | None:
    derivatives = photo.get("derivatives") or {}
    if not derivatives:
        return None
    return max(derivatives.values(), key=lambda d: int(d.get("width", 0)))


async def _post(host: str, token: str, path: str, body: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10) as client:
        return await client.post(f"https://{host}/{token}/sharedstreams/{path}", json=body)


async def _webstream(token: str) -> httpx.Response:
    host_cache_key = f"icloud_shared_album:host:{token}"
    host = cache.get(host_cache_key) or _DEFAULT_HOST

    response = await _post(host, token, "webstream", {"streamCtag": None})
    redirect_host = response.headers.get("X-Apple-MMe-Host")
    if redirect_host and redirect_host != host:
        response = await _post(redirect_host, token, "webstream", {"streamCtag": None})
        host = redirect_host
    response.raise_for_status()

    cache.set(host_cache_key, host, _HOST_CACHE_TTL_SECONDS)
    return response


async def fetch_photos(token: str) -> list[dict[str, Any]]:
    """Metadata for every photo in the shared album, largest-derivative first.

    Cached briefly (`_PHOTO_LIST_CACHE_TTL_SECONDS`) since this is called
    both when polling a widget's summary/detail and once per photo when
    serving `/api/photos/{widget_id}/{guid}` — without caching, viewing a
    slideshow would hit Apple's webstream endpoint once per image.
    """
    cache_key = f"icloud_shared_album:photos:{token}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    response = await _webstream(token)
    photos = []
    for photo in response.json().get("photos", []):
        derivative = _largest_derivative(photo)
        if derivative is None:
            continue
        photos.append(
            {
                "guid": photo["photoGuid"],
                "checksum": derivative["checksum"],
                "width": int(derivative.get("width", 0)),
                "height": int(derivative.get("height", 0)),
            }
        )

    cache.set(cache_key, photos, _PHOTO_LIST_CACHE_TTL_SECONDS)
    return photos


async def fetch_asset_url(token: str, guid: str, checksum: str) -> str | None:
    """A direct, short-lived CDN download URL for one photo's checksum."""
    cache_key = f"icloud_shared_album:asset:{token}:{guid}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    host_cache_key = f"icloud_shared_album:host:{token}"
    host = cache.get(host_cache_key) or _DEFAULT_HOST
    response = await _post(host, token, "webasseturls", {"photoGuids": [guid]})
    response.raise_for_status()

    items = response.json().get("items", {})
    asset = items.get(checksum)
    if asset is None:
        return None

    url = f"https://{asset['url_location']}{asset['url_path']}"
    cache.set(cache_key, url, _ASSET_URL_CACHE_TTL_SECONDS)
    return url
