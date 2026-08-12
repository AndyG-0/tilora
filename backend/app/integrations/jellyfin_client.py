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
            audio_streams.append({
                "index": idx,
                "display_title": display_title,
                "language": lang,
                "codec": codec,
                "channels": stream.get("Channels", 2),
                "is_default": bool(stream.get("IsDefault")),
            })
        elif stype == "Subtitle":
            subtitle_streams.append({
                "index": idx,
                "display_title": display_title,
                "language": lang,
                "codec": codec,
                "is_default": bool(stream.get("IsDefault")),
                "is_forced": bool(stream.get("IsForced")),
            })
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
    audio_stream_index: int | None = None,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    conn = await resolve_connection(settings, widget_id)
    headers = dict(conn.headers)
    if range_header:
        headers["Range"] = range_header

    playback_mode = settings.get("playback_mode", "compatible")
    if playback_mode == "direct":
        params: dict[str, Any] = {"static": "true"}
    elif playback_mode == "compatible_video":
        params = {
            "static": "false",
            "VideoCodec": "h264",
            "AudioCodec": "aac",
            "MaxAudioChannels": "2",
            "Container": "mp4",
        }
    else:
        params = {
            "static": "false",
            "VideoCodec": "copy",
            "AudioCodec": "aac",
            "MaxAudioChannels": "2",
            "Container": "mp4",
        }

    if audio_stream_index is not None:
        params["AudioStreamIndex"] = str(audio_stream_index)

    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=None, write=10, pool=10))
    request = client.build_request("GET", f"{conn.base_url}/Videos/{item_id}/stream", headers=headers, params=params)
    response = await client.send(request, stream=True)
    return client, response
