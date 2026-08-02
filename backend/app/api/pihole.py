"""Pi-hole test-connection and blocking-control routes.

A dedicated router rather than folding into `widgets.py`, since both routes
need Pi-hole-specific behavior the generic summary/detail/settings endpoints
don't cover: testing not-yet-saved connection settings, and immediately
invalidating cached summary/detail data after a blocking-state change so the
tile doesn't show a stale status until the next refresh interval. Settings
are read from the *live* registered plugin instance (not
`app.config.widget_config`, which only reflects `dashboard.yaml` and misses
DB-persisted overrides) so a connection just saved from the widget's detail
view works immediately — same reasoning as `app/api/jellyfin.py`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.integrations import pihole_client
from app.plugins.base import registry
from app.plugins.pihole.plugin import PiholePlugin
from app.storage.cache import cache

router = APIRouter(prefix="/api/pihole", tags=["pihole"])


def _get_plugin(widget_id: str) -> PiholePlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, PiholePlugin):
        raise HTTPException(status_code=404, detail=f"Unknown Pi-hole widget '{widget_id}'")
    return plugin


@router.post("/{widget_id}/test-connection")
async def test_connection(widget_id: str, payload: dict[str, Any]):
    plugin = _get_plugin(widget_id)
    candidate_settings = {**plugin.config["settings"], **payload}
    try:
        version = await pihole_client.test_connection(candidate_settings, widget_id)
    except pihole_client.PiholeError as exc:
        return {"ok": False, "version": None, "error": str(exc)}
    return {"ok": True, "version": version, "error": None}


@router.post("/{widget_id}/blocking")
async def set_blocking(widget_id: str, payload: dict[str, Any]):
    plugin = _get_plugin(widget_id)
    try:
        result = await pihole_client.set_blocking(
            plugin.config["settings"], widget_id, bool(payload["enabled"]), payload.get("timer")
        )
    except pihole_client.PiholeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cache.delete(f"summary:{widget_id}")
    cache.delete(f"detail:{widget_id}")
    return result
