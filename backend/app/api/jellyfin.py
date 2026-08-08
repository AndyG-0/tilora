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
