"""Jellyfin HTTP client for the Jellyfin plugin.

Two auth modes: a server-issued API key (Dashboard -> API Keys), sent as
`X-Emby-Token` with no live login step, or a real user's username/password,
exchanged once for an access token via `/Users/AuthenticateByName` and
cached in-memory (see `storage/cache.py`) until a 401 forces re-auth. The
API-key path has no user context, so it falls back to the server-wide
library/item endpoints instead of the personalized `/Users/{id}/...` ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx

from app.storage.cache import cache
from app.update_check import CURRENT_VERSION

_TOKEN_TTL_SECONDS = 12 * 60 * 60
_DEVICE_NAME = "Tilora"


class JellyfinError(Exception):
    """Raised when a Jellyfin server can't be reached or rejects a request."""


@dataclass
class JellyfinConnection:
    base_url: str
    headers: dict[str, str]
    user_id: str | None


def is_configured(settings: dict[str, Any]) -> bool:
    if not settings.get("host"):
        return False
    if settings.get("auth_mode") == "password":
        return bool(settings.get("username") and settings.get("password"))
    return bool(settings.get("api_key"))


def _base_url(settings: dict[str, Any]) -> str:
    scheme = "https" if settings.get("use_https") else "http"
    return f"{scheme}://{settings['host']}:{settings.get('port', 8096)}"


def _auth_header(widget_id: str) -> dict[str, str]:
    return {
        "Authorization": (
            f'MediaBrowser Client="{_DEVICE_NAME}", Device="{_DEVICE_NAME}", '
            f'DeviceId="dashboard-{widget_id}", Version="{CURRENT_VERSION}"'
        )
    }


async def _authenticate_by_name(base_url: str, widget_id: str, username: str, password: str) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                f"{base_url}/Users/AuthenticateByName",
                json={"Username": username, "Pw": password},
                headers=_auth_header(widget_id),
            )
        except httpx.HTTPError as exc:
            raise JellyfinError(f"Could not reach the Jellyfin server: {exc}") from exc
    if response.status_code == 401:
        raise JellyfinError("Jellyfin rejected that username/password.")
    if response.status_code >= 400:
        raise JellyfinError(f"Jellyfin login failed (HTTP {response.status_code}).")

    data = response.json()
    token = {"access_token": data["AccessToken"], "user_id": data["User"]["Id"]}
    cache.set(f"jellyfin_token:{widget_id}", token, _TOKEN_TTL_SECONDS)
    return token


async def resolve_connection(
    settings: dict[str, Any], widget_id: str, *, force_reauth: bool = False
) -> JellyfinConnection:
    base_url = _base_url(settings)

    if settings.get("auth_mode") == "password":
        cache_key = f"jellyfin_token:{widget_id}"
        token = None if force_reauth else cache.get(cache_key)
        if token is None:
            username, password = settings.get("username"), settings.get("password")
            if not username or not password:
                raise JellyfinError("A Jellyfin username and password are required.")
            token = await _authenticate_by_name(base_url, widget_id, username, password)
        return JellyfinConnection(
            base_url=base_url,
            headers={"X-Emby-Token": token["access_token"]},
            user_id=token["user_id"],
        )

    api_key = settings.get("api_key")
    if not api_key:
        raise JellyfinError("A Jellyfin API key is required.")
    return JellyfinConnection(base_url=base_url, headers={"X-Emby-Token": api_key}, user_id=None)


async def _request(
    method: str,
    path: str,
    *,
    settings: dict[str, Any],
    widget_id: str,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    conn = await resolve_connection(settings, widget_id)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, f"{conn.base_url}{path}", headers=conn.headers, params=params)
    except httpx.HTTPError as exc:
        raise JellyfinError(f"Could not reach the Jellyfin server: {exc}") from exc

    if response.status_code == 401 and settings.get("auth_mode") == "password":
        # The cached access token expired/was revoked server-side — re-auth
        # once and retry, rather than surfacing a stale-token error.
        conn = await resolve_connection(settings, widget_id, force_reauth=True)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(method, f"{conn.base_url}{path}", headers=conn.headers, params=params)
        except httpx.HTTPError as exc:
            raise JellyfinError(f"Could not reach the Jellyfin server: {exc}") from exc

    if response.status_code >= 400:
        raise JellyfinError(f"Jellyfin request failed (HTTP {response.status_code}).")
    return response


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    response = await _request("GET", "/System/Info", settings=settings, widget_id=widget_id)
    return response.json().get("ServerName", "Jellyfin")


def _item_dict(item: dict[str, Any]) -> dict[str, Any]:
    runtime_ticks = item.get("RunTimeTicks")
    return {
        "id": item["Id"],
        "name": item.get("Name", ""),
        "type": item.get("Type", ""),
        "overview": item.get("Overview"),
        "year": item.get("ProductionYear"),
        "is_folder": bool(item.get("IsFolder")),
        "has_poster": bool((item.get("ImageTags") or {}).get("Primary")),
        "runtime_minutes": round(runtime_ticks / 600_000_000) if runtime_ticks else None,
    }


async def list_children(settings: dict[str, Any], widget_id: str, parent_id: str | None) -> list[dict[str, Any]]:
    conn = await resolve_connection(settings, widget_id)

    if parent_id is None:
        path = f"/Users/{conn.user_id}/Views" if conn.user_id else "/Library/MediaFolders"
        response = await _request("GET", path, settings=settings, widget_id=widget_id)
        items = response.json().get("Items", [])
        return [_item_dict(item) for item in items]

    path = f"/Users/{conn.user_id}/Items" if conn.user_id else "/Items"
    response = await _request(
        "GET",
        path,
        settings=settings,
        widget_id=widget_id,
        params={"ParentId": parent_id, "Fields": "Overview", "SortBy": "IsFolder,SortName", "SortOrder": "Ascending"},
    )
    items = response.json().get("Items", [])
    return [_item_dict(item) for item in items]


async def list_recent_items(settings: dict[str, Any], widget_id: str, limit: int = 8) -> list[dict[str, Any]]:
    conn = await resolve_connection(settings, widget_id)
    path = f"/Users/{conn.user_id}/Items" if conn.user_id else "/Items"
    response = await _request(
        "GET",
        path,
        settings=settings,
        widget_id=widget_id,
        params={
            "Recursive": "true",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "IncludeItemTypes": "Movie,Episode",
            "Limit": limit,
        },
    )
    items = response.json().get("Items", [])
    return [_item_dict(item) for item in items]


async def list_resume_items(settings: dict[str, Any], widget_id: str, limit: int = 8) -> list[dict[str, Any]]:
    conn = await resolve_connection(settings, widget_id)
    if not conn.user_id:
        # api_key auth has no user context, so there's no personal "continue
        # watching" list to fall back to (unlike list_recent_items, which has
        # a server-wide equivalent).
        return []
    response = await _request(
        "GET",
        f"/Users/{conn.user_id}/Items/Resume",
        settings=settings,
        widget_id=widget_id,
        params={"Limit": limit, "Fields": "Overview"},
    )
    items = response.json().get("Items", [])
    return [_item_dict(item) for item in items]


# Posters are shown as small tiles (a few cm across, even at kiosk-display
# DPI) — asking Jellyfin for the original artwork (often several MB, easily
# 2000px+ on a side) wastes bandwidth and, worse, CPU decoding it in the
# browser on underpowered hardware like a Raspberry Pi. Capping the source
# size server-side is strictly better than downscaling after the fact.
_IMAGE_MAX_WIDTH = 400
_IMAGE_QUALITY = 90


async def fetch_image_bytes(settings: dict[str, Any], widget_id: str, item_id: str) -> tuple[bytes, str] | None:
    try:
        response = await _request(
            "GET",
            f"/Items/{item_id}/Images/Primary",
            settings=settings,
            widget_id=widget_id,
            params={"maxWidth": _IMAGE_MAX_WIDTH, "quality": _IMAGE_QUALITY},
        )
    except JellyfinError:
        return None
    return response.content, response.headers.get("content-type", "image/jpeg")


async def get_item_detail(settings: dict[str, Any], widget_id: str, item_id: str) -> dict[str, Any]:
    conn = await resolve_connection(settings, widget_id)
    path = f"/Users/{conn.user_id}/Items/{item_id}" if conn.user_id else f"/Items/{item_id}"
    response = await _request(
        "GET",
        path,
        settings=settings,
        widget_id=widget_id,
        params={"Fields": "Overview,MediaStreams,Chapters,MediaSources"},
    )
    data = response.json()
    runtime_ticks = data.get("RunTimeTicks")

    chapters = []
    for ch in data.get("Chapters") or []:
        start_seconds = round((ch.get("StartPositionTicks") or 0) / 10_000_000, 2)
        chapters.append({"name": ch.get("Name", ""), "start_seconds": start_seconds})

    audio_streams = []
    subtitle_streams = []
    video_stream = None

    for stream in data.get("MediaStreams") or []:
        stype = stream.get("Type")
        idx = stream.get("Index", 0)
        display_title = stream.get("DisplayTitle") or stream.get("Title") or f"Track {idx}"
        lang = stream.get("Language", "")
        codec = stream.get("Codec", "")
        if stype == "Audio":
            audio_streams.append(
                {
                    "index": idx,
                    "display_title": display_title,
                    "language": lang,
                    "codec": codec,
                    "channels": stream.get("Channels", 2),
                    "is_default": bool(stream.get("IsDefault")),
                }
            )
        elif stype == "Subtitle":
            subtitle_streams.append(
                {
                    "index": idx,
                    "display_title": display_title,
                    "language": lang,
                    "codec": codec,
                    "is_default": bool(stream.get("IsDefault")),
                    "is_forced": bool(stream.get("IsForced")),
                }
            )
        elif stype == "Video" and video_stream is None:
            video_stream = {
                "codec": codec,
                "width": stream.get("Width"),
                "height": stream.get("Height"),
                "aspect_ratio": stream.get("AspectRatio", ""),
                "framerate": stream.get("RealFrameRate") or stream.get("AverageFrameRate"),
                "bitrate": stream.get("BitRate"),
            }

    container = data.get("Container")
    if not container and data.get("MediaSources"):
        container = data["MediaSources"][0].get("Container")

    return {
        "id": data.get("Id", item_id),
        "name": data.get("Name", ""),
        "type": data.get("Type", ""),
        "overview": data.get("Overview"),
        "year": data.get("ProductionYear"),
        "runtime_minutes": round(runtime_ticks / 600_000_000) if runtime_ticks else None,
        "container": container,
        "video_stream": video_stream,
        "audio_streams": audio_streams,
        "subtitle_streams": subtitle_streams,
        "chapters": chapters,
    }


async def fetch_subtitle_vtt(settings: dict[str, Any], widget_id: str, item_id: str, index: int) -> bytes | None:
    try:
        response = await _request(
            "GET",
            f"/Videos/{item_id}/Subtitles/{index}/0/Stream.vtt",
            settings=settings,
            widget_id=widget_id,
        )
        return response.content
    except JellyfinError:
        return None


async def open_video_stream(
    settings: dict[str, Any],
    widget_id: str,
    item_id: str,
    range_header: str | None,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Proxy the *original file bytes* verbatim — genuine Direct Play.

    Only used when the frontend has already confirmed (via `canPlayType`)
    that the browser can natively decode the source container/codecs;
    everything else goes through `open_hls_playlist`/`open_hls_resource`
    instead, which is why this no longer branches on a playback-mode
    setting the way it once did.
    """
    conn = await resolve_connection(settings, widget_id)
    headers = dict(conn.headers)
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=None, write=10, pool=10))
    request = client.build_request(
        "GET", f"{conn.base_url}/Videos/{item_id}/stream", headers=headers, params={"static": "true"}
    )
    response = await client.send(request, stream=True)
    return client, response


async def open_hls_playlist(
    settings: dict[str, Any],
    widget_id: str,
    item_id: str,
    *,
    audio_stream_index: int | None = None,
    play_session_id: str,
) -> str:
    """Fetch Jellyfin's own HLS master playlist for `item_id`.

    h264 is always safe; hevc is included too since Safari/iOS hardware-
    decodes it, letting Jellyfin skip a video re-encode when only the
    container/audio needs fixing. The playlist is small, so it's read fully
    here rather than streamed — the caller rewrites its URIs before
    returning it to the browser (see `rewrite_hls_playlist`).
    """
    conn = await resolve_connection(settings, widget_id)
    params: dict[str, Any] = {
        "VideoCodec": "h264,hevc",
        "AudioCodec": "aac",
        "MaxAudioChannels": "2",
        "DeviceId": f"dashboard-{widget_id}",
        "PlaySessionId": play_session_id,
        # Jellyfin 400s without this ("The mediaSourceId field is required").
        # Tilora only ever plays an item's default media source, whose Id is
        # the item Id itself.
        "MediaSourceId": item_id,
    }
    if audio_stream_index is not None:
        params["AudioStreamIndex"] = str(audio_stream_index)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{conn.base_url}/Videos/{item_id}/master.m3u8",
                headers=conn.headers,
                params=params,
            )
    except httpx.HTTPError as exc:
        raise JellyfinError(f"Could not reach the Jellyfin server: {exc}") from exc
    if response.status_code >= 400:
        raise JellyfinError(f"Jellyfin HLS request failed (HTTP {response.status_code}).")
    return response.text


async def open_hls_resource(
    settings: dict[str, Any], widget_id: str, path: str, query: str
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Generic streamed passthrough for a segment or nested variant playlist
    referenced by an HLS playlist. `path`/`query` come from
    `rewrite_hls_playlist`'s own rewriting of what Jellyfin's playlist
    referenced — never taken raw from the client — so this stays a closed
    proxy rather than an open one.
    """
    conn = await resolve_connection(settings, widget_id)
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=None, write=10, pool=10))
    request = client.build_request(
        "GET", f"{conn.base_url}{path}", headers=conn.headers, params=httpx.QueryParams(query)
    )
    response = await client.send(request, stream=True)
    return client, response


def rewrite_hls_playlist(text: str, widget_id: str, item_id: str, upstream_path: str) -> str:
    """Rewrite every URI line of an m3u8 playlist to an opaque
    `hls-resource` URL pointing back at this backend, so the browser never
    talks to Jellyfin (or sees its credentials) directly.

    Works for both a media playlist (segment URIs) and a master playlist
    (nested `#EXT-X-STREAM-INF` variant playlist URIs) — the same rewrite
    applies to both since it's just "any non-comment, non-blank line".
    `upstream_path` is the path this playlist itself was fetched from
    (`/Videos/{id}/master.m3u8` for the master, or a prior rewrite's
    resolved path for a nested playlist) — relative URIs in the playlist are
    resolved against it, not against the item's root, since a nested
    playlist's own segments are typically relative to *its* location.
    """
    lines = text.splitlines()
    rewritten = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            rewritten.append(line)
            continue
        resolved = urljoin(upstream_path, stripped)
        split = urlsplit(resolved)
        upstream_path_and_query = split.path + (f"?{split.query}" if split.query else "")
        rewritten.append(
            f"/api/jellyfin/{widget_id}/hls-resource/{item_id}?path={quote(upstream_path_and_query, safe='')}"
        )
    return "\n".join(rewritten) + ("\n" if text.endswith("\n") else "")


# .NET TimeSpan ticks (100ns units) — the unit Jellyfin's playstate APIs use
# for every position field.
_TICKS_PER_SECOND = 10_000_000


async def report_playback_start(settings: dict[str, Any], widget_id: str, item_id: str, play_session_id: str) -> None:
    """Best-effort: tell Jellyfin a transcode session has begun playing.

    Without this, Jellyfin only learns about the session indirectly from the
    HLS segment requests it's serving, which makes its own "continue
    watching" resume state lag well behind actual playback. Reporting start/
    progress/stop explicitly (mirroring what Jellyfin's own web/mobile apps
    do) keeps that state accurate immediately. Errors are swallowed; this is
    telemetry, not a step playback depends on.
    """
    try:
        conn = await resolve_connection(settings, widget_id)
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{conn.base_url}/Sessions/Playing",
                headers=conn.headers,
                json={
                    "ItemId": item_id,
                    "MediaSourceId": item_id,
                    "PlaySessionId": play_session_id,
                    "PlayMethod": "Transcode",
                    "CanSeek": True,
                },
            )
    except (JellyfinError, httpx.HTTPError):
        pass


async def report_playback_progress(
    settings: dict[str, Any],
    widget_id: str,
    item_id: str,
    play_session_id: str,
    position_seconds: float,
    *,
    is_paused: bool = False,
) -> None:
    """Best-effort heartbeat so Jellyfin's resume position stays current
    while a transcode session is playing, rather than only updating once the
    session ends. See `report_playback_start` for why this matters.
    """
    try:
        conn = await resolve_connection(settings, widget_id)
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{conn.base_url}/Sessions/Playing/Progress",
                headers=conn.headers,
                json={
                    "ItemId": item_id,
                    "MediaSourceId": item_id,
                    "PlaySessionId": play_session_id,
                    "PlayMethod": "Transcode",
                    "PositionTicks": round(position_seconds * _TICKS_PER_SECOND),
                    "IsPaused": is_paused,
                },
            )
    except (JellyfinError, httpx.HTTPError):
        pass


async def stop_playback_session(
    settings: dict[str, Any], widget_id: str, item_id: str, play_session_id: str, position_seconds: float
) -> None:
    """Best-effort: tell Jellyfin to end its own transcode job promptly on
    player close, mirroring the discipline HDHomeRun's teardown applies to
    killing its ffmpeg subprocess — just backed by Jellyfin's session API
    instead of a subprocess Tilora owns. Reports the final position so
    Jellyfin's resume state reflects exactly where playback stopped, not just
    the last progress heartbeat. Errors are swallowed; this is cleanup, not a
    step playback depends on.
    """
    try:
        conn = await resolve_connection(settings, widget_id)
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{conn.base_url}/Sessions/Playing/Stopped",
                headers=conn.headers,
                json={
                    "ItemId": item_id,
                    "MediaSourceId": item_id,
                    "PlaySessionId": play_session_id,
                    "PositionTicks": round(position_seconds * _TICKS_PER_SECOND),
                },
            )
    except (JellyfinError, httpx.HTTPError):
        pass
