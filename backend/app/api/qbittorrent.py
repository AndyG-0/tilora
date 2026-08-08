"""qBittorrent test-connection route.

A dedicated router rather than folding into `widgets.py`, since testing
not-yet-saved connection settings needs qBittorrent-specific behavior the
generic summary/detail/settings endpoints don't cover — same reasoning as
`app/api/pihole.py`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, require_write_access
from app.integrations import qbittorrent_client
from app.plugins.base import registry
from app.plugins.qbittorrent.plugin import QBittorrentPlugin

router = APIRouter(prefix="/api/qbittorrent", tags=["qbittorrent"], dependencies=[Depends(get_current_user)])


def _get_plugin(widget_id: str) -> QBittorrentPlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, QBittorrentPlugin):
        raise HTTPException(status_code=404, detail=f"Unknown qBittorrent widget '{widget_id}'")
    return plugin


@router.post("/{widget_id}/test-connection")
async def test_connection(widget_id: str, payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    plugin = _get_plugin(widget_id)
    require_write_access(plugin, user)
    candidate_settings = {**plugin.config["settings"], **payload}
    try:
        version = await qbittorrent_client.test_connection(candidate_settings, widget_id)
    except qbittorrent_client.QBittorrentError as exc:
        return {"ok": False, "version": None, "error": str(exc)}
    return {"ok": True, "version": version, "error": None}
