"""Jellyfin library browsing and media proxy routes.

A dedicated router rather than folding into `widgets.py`, since most of
these routes stream bytes (images, video) or need Jellyfin-specific query
params rather than the generic summary/detail JSON shape. Settings are read
from the *live* registered plugin instance (not `app.config.widget_config`,
which only reflects `dashboard.yaml` and misses DB-persisted overrides) so a
connection change made via `app/api/network_settings.py` takes effect
immediately.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.integrations import jellyfin_client
from app.plugins.base import registry
from app.plugins.jellyfin.plugin import JellyfinPlugin

router = APIRouter(prefix="/api/jellyfin", tags=["jellyfin"], dependencies=[Depends(get_current_user)])

_FORWARDED_STREAM_HEADERS = ("content-type", "content-length", "content-range", "accept-ranges")


def _get_plugin(widget_id: str) -> JellyfinPlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, JellyfinPlugin):
        raise HTTPException(status_code=404, detail=f"Unknown Jellyfin widget '{widget_id}'")
    return plugin


@router.get("/{widget_id}/libraries")
async def list_libraries(widget_id: str):
    plugin = _get_plugin(widget_id)
    try:
        return await jellyfin_client.list_children(plugin.config["settings"], widget_id, parent_id=None)
    except jellyfin_client.JellyfinError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{widget_id}/items")
async def list_items(widget_id: str, parent_id: str):
    plugin = _get_plugin(widget_id)
    try:
        return await jellyfin_client.list_children(plugin.config["settings"], widget_id, parent_id)
    except jellyfin_client.JellyfinError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{widget_id}/images/{item_id}")
async def get_image(widget_id: str, item_id: str):
    plugin = _get_plugin(widget_id)
    result = await jellyfin_client.fetch_image_bytes(plugin.config["settings"], widget_id, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Image not found")
    content, content_type = result
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/{widget_id}/detail/{item_id}")
async def get_item_detail(widget_id: str, item_id: str):
    plugin = _get_plugin(widget_id)
    try:
        return await jellyfin_client.get_item_detail(plugin.config["settings"], widget_id, item_id)
    except jellyfin_client.JellyfinError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{widget_id}/subtitles/{item_id}/{stream_index}.vtt")
async def get_subtitle(widget_id: str, item_id: str, stream_index: int):
    plugin = _get_plugin(widget_id)
    content = await jellyfin_client.fetch_subtitle_vtt(plugin.config["settings"], widget_id, item_id, stream_index)
    if content is None:
        raise HTTPException(status_code=404, detail="Subtitle track not found")
    return Response(content=content, media_type="text/vtt", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/{widget_id}/stream/{item_id}")
async def stream_item(widget_id: str, item_id: str, request: Request):
    plugin = _get_plugin(widget_id)
    try:
        client, upstream = await jellyfin_client.open_video_stream(
            plugin.config["settings"], widget_id, item_id, request.headers.get("range")
        )
    except jellyfin_client.JellyfinError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if upstream.status_code >= 400:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=upstream.status_code, detail="Could not stream video")

    async def body():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    headers = {k: v for k, v in upstream.headers.items() if k.lower() in _FORWARDED_STREAM_HEADERS}
    return StreamingResponse(body(), status_code=upstream.status_code, headers=headers)


@router.get("/{widget_id}/hls/{item_id}/master.m3u8")
async def hls_master_playlist(
    widget_id: str, item_id: str, play_session_id: str, audio_stream_index: int | None = None
):
    plugin = _get_plugin(widget_id)
    try:
        text = await jellyfin_client.open_hls_playlist(
            plugin.config["settings"],
            widget_id,
            item_id,
            audio_stream_index=audio_stream_index,
            play_session_id=play_session_id,
        )
    except jellyfin_client.JellyfinError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    rewritten = jellyfin_client.rewrite_hls_playlist(text, widget_id, item_id, f"/Videos/{item_id}/master.m3u8")
    return Response(content=rewritten, media_type="application/vnd.apple.mpegurl")


@router.get("/{widget_id}/hls-resource/{item_id}")
async def hls_resource(widget_id: str, item_id: str, path: str):
    plugin = _get_plugin(widget_id)
    parsed = urlsplit(path)
    try:
        client, upstream = await jellyfin_client.open_hls_resource(
            plugin.config["settings"], widget_id, parsed.path, parsed.query
        )
    except jellyfin_client.JellyfinError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if upstream.status_code >= 400:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=upstream.status_code, detail="Could not fetch HLS resource")

    content_type = upstream.headers.get("content-type", "")
    if "mpegurl" in content_type.lower() or parsed.path.endswith(".m3u8"):
        # A nested variant playlist (rather than a media segment) — read it
        # fully and rewrite its own URIs the same way the master playlist's
        # were, resolved relative to *this* playlist's own upstream path.
        raw = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        rewritten = jellyfin_client.rewrite_hls_playlist(
            raw.decode("utf-8", errors="replace"), widget_id, item_id, parsed.path
        )
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl")

    async def body():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    headers = {k: v for k, v in upstream.headers.items() if k.lower() in _FORWARDED_STREAM_HEADERS}
    return StreamingResponse(body(), status_code=upstream.status_code, headers=headers)


@router.post("/{widget_id}/playback-started/{item_id}")
async def playback_started(widget_id: str, item_id: str, play_session_id: str):
    plugin = _get_plugin(widget_id)
    await jellyfin_client.report_playback_start(plugin.config["settings"], widget_id, item_id, play_session_id)
    return {"status": "ok"}


@router.post("/{widget_id}/playback-progress/{item_id}")
async def playback_progress(
    widget_id: str, item_id: str, play_session_id: str, position_seconds: float, is_paused: bool = False
):
    plugin = _get_plugin(widget_id)
    await jellyfin_client.report_playback_progress(
        plugin.config["settings"], widget_id, item_id, play_session_id, position_seconds, is_paused=is_paused
    )
    return {"status": "ok"}


@router.post("/{widget_id}/playback-stopped/{item_id}")
async def playback_stopped(widget_id: str, item_id: str, play_session_id: str, position_seconds: float = 0):
    plugin = _get_plugin(widget_id)
    await jellyfin_client.stop_playback_session(
        plugin.config["settings"], widget_id, item_id, play_session_id, position_seconds
    )
    return {"status": "ok"}
