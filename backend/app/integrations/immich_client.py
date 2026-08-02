"""Client for a self-hosted Immich (https://immich.app) photo server.

Immich exposes an OpenAPI-documented REST API (spec:
immich-app/immich `open-api/immich-openapi-specs.json`). Confirmed against
the live spec for the current stable release (v3.1.0, published
2026-07-29):

- Auth: an `x-api-key` header carrying a user-generated API key (Immich
  account settings -> API Keys). Confirmed via the spec's
  `components.securitySchemes.api_key` (`{"type": "apiKey", "in": "header",
  "name": "x-api-key"}`) — no OAuth/2FA, unlike `icloud_photos`.
- Server URL: the spec's top-level `servers` entry is `[{"url": "/api"}]`
  (paths relative to it), and Immich's own docs/CLI/mobile-app instructions
  consistently have users enter the server URL *including* the `/api`
  suffix (e.g. `http://192.168.1.216:2283/api` — see
  https://docs.immich.app/features/command-line-interface). So `base_url`
  here is expected to already include `/api`; `normalize_base_url` only
  strips a stray trailing slash, it does not append `/api` itself.
- Album contents: `GET /albums/{id}` (AlbumResponseDto) no longer embeds an
  `assets` array as of this version — confirmed by diffing the schema
  against the spec (only `assetCount`, no `assets` property). The
  documented way to list an album's assets is `POST /search/metadata` with
  `{"albumIds": [id], "page": N, "size": M}` (MetadataSearchDto), which
  returns `SearchResponseDto.assets` (`SearchAssetResponseDto`:
  `{count, items: AssetResponseDto[], nextPage, total}` — `total` is
  deprecated since v3.0.0, so pagination here follows `nextPage` instead).
  Each `AssetResponseDto` has `id` (uuid), `originalFileName`, `width`,
  `height` (both nullable), `type` (enum `IMAGE|VIDEO|AUDIO|OTHER`),
  `isTrashed`.
- Asset bytes: `GET /assets/{id}/thumbnail?size=preview|thumbnail|fullsize`
  (falls back through Immich's own generated derivatives — `preview` is a
  resized, display-quality JPEG, well suited to a slideshow) and
  `GET /assets/{id}/original` (the untouched original file, which for RAW
  sources could be large). This client uses the thumbnail endpoint at
  `size=preview` for slideshow display. Both return
  `application/octet-stream` per the spec (no fixed content-type), so the
  actual `content-type` response header is passed through with a
  `image/jpeg` fallback.

Since there's no live server available to verify error-response shapes
against, every external field access uses `.get()` with a default, and any
non-2xx response or unexpected JSON shape raises `ImmichError` (never an
unhandled exception) — same defensive style as `gametools_client.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

_REQUEST_TIMEOUT_SECONDS = 15
_SEARCH_PAGE_SIZE = 200
# Safety cap on pagination loops (500 pages * 200/page = 100,000 assets) so a
# server returning a malformed/cyclic `nextPage` token can't hang the
# background indexer forever.
_MAX_SEARCH_PAGES = 500


class ImmichError(Exception):
    """Raised when the Immich server can't be reached or returns something unusable."""


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("base_url")) and bool(settings.get("api_key")) and bool(settings.get("album_id"))


def normalize_base_url(base_url: str) -> str:
    """Strips a trailing slash. Does not append `/api` — see module docstring."""
    return base_url.rstrip("/")


async def _request(method: str, url: str, api_key: str, **kwargs: Any) -> httpx.Response:
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        try:
            return await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ImmichError(f"Could not reach the Immich server: {exc}") from exc


def _error_message(response: httpx.Response, what: str) -> str:
    if response.status_code in (401, 403):
        return (
            "Immich rejected the request — check the API key, and that it has the required "
            "permissions (album.read / asset.read / asset.download)."
        )
    message = f"Immich {what} request failed (HTTP {response.status_code})."
    try:
        body = response.json()
    except ValueError:
        return message
    if isinstance(body, dict):
        detail = body.get("message")
        if isinstance(detail, str) and detail:
            return detail
        if isinstance(detail, list) and detail:
            return "; ".join(str(m) for m in detail)
    return message


async def _post_json(base_url: str, api_key: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await _request("POST", f"{base_url}{path}", api_key, json=body)
    if response.status_code >= 400:
        raise ImmichError(_error_message(response, "album search"))
    try:
        data = response.json()
    except ValueError as exc:
        raise ImmichError(f"Unexpected (non-JSON) response from the Immich server: {exc}") from exc
    if not isinstance(data, dict):
        raise ImmichError("Unexpected response shape from the Immich server.")
    return data


def _asset_dict(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset.get("id", "") or "",
        "filename": asset.get("originalFileName", "") or "",
        "width": asset.get("width") or 0,
        "height": asset.get("height") or 0,
    }


async def iter_album_asset_chunks(
    base_url: str, api_key: str, album_id: str, page_size: int = _SEARCH_PAGE_SIZE
) -> AsyncIterator[list[dict[str, Any]]]:
    """Metadata for every image asset in the given album, yielded in
    bounded-memory pages — for the background index scan (see
    app.plugins.photos.indexer), mirroring icloud_photos.iter_photo_chunks.

    Uses `POST /search/metadata` filtered by `albumIds`, since `GET
    /albums/{id}` no longer returns an assets array (see module docstring).
    Non-image assets (videos/audio/other) and trashed assets are skipped —
    this is a photo slideshow. Yields nothing (not an error) if any of
    base_url/api_key/album_id is missing, an empty album, or a response
    shape this client doesn't recognize; raises `ImmichError` on
    network/HTTP failures, same as the rest of this module.
    """
    if not (base_url and api_key and album_id):
        return

    page: int | None = 1
    seen_pages: set[int] = set()
    for _ in range(_MAX_SEARCH_PAGES):
        if page is None or page in seen_pages:
            return
        seen_pages.add(page)
        data = await _post_json(
            base_url, api_key, "/search/metadata", {"albumIds": [album_id], "page": page, "size": page_size}
        )
        assets = data.get("assets")
        items = assets.get("items") if isinstance(assets, dict) else None
        if not isinstance(items, list):
            return

        chunk = [
            _asset_dict(asset)
            for asset in items
            if isinstance(asset, dict) and asset.get("type") == "IMAGE" and not asset.get("isTrashed")
        ]
        if chunk:
            yield chunk

        next_page = assets.get("nextPage") if isinstance(assets, dict) else None
        if not next_page:
            return
        try:
            page = int(next_page)
        except (TypeError, ValueError):
            return


async def fetch_asset_bytes(
    base_url: str, api_key: str, asset_id: str, size: str = "preview"
) -> tuple[bytes, str] | None:
    """Raw bytes + content-type for one asset's display-quality thumbnail.

    Returns `None` (not an error) for a missing/deleted asset (Immich
    returns HTTP 404), same "not found is not an error" convention as
    `icloud_photos.fetch_photo_bytes`/`icloud_shared_album.fetch_asset_url`.
    Raises `ImmichError` for any other failure.
    """
    if not (base_url and api_key and asset_id):
        return None

    response = await _request("GET", f"{base_url}/assets/{asset_id}/thumbnail", api_key, params={"size": size})
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise ImmichError(_error_message(response, "asset"))

    content_type = response.headers.get("content-type") or "image/jpeg"
    return response.content, content_type
