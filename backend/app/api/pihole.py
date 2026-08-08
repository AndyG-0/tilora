"""Pi-hole blocking-control route.

A dedicated router rather than folding into `widgets.py`, since it needs to
immediately invalidate cached summary/detail data after a blocking-state
change so the tile doesn't show a stale status until the next refresh
interval. Connection settings are edited at the network level now (see
`app/api/network_settings.py`), not per-widget.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, require_write_access
from app.integrations import pihole_client
from app.plugins.base import registry
from app.plugins.pihole.plugin import PiholePlugin
from app.storage.cache import cache

router = APIRouter(prefix="/api/pihole", tags=["pihole"], dependencies=[Depends(get_current_user)])


def _get_plugin(widget_id: str) -> PiholePlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, PiholePlugin):
        raise HTTPException(status_code=404, detail=f"Unknown Pi-hole widget '{widget_id}'")
    return plugin


@router.post("/{widget_id}/blocking")
async def set_blocking(widget_id: str, payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    plugin = _get_plugin(widget_id)
    require_write_access(plugin, user)
    try:
        result = await pihole_client.set_blocking(
            plugin.config["settings"], widget_id, bool(payload["enabled"]), payload.get("timer")
        )
    except pihole_client.PiholeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cache.delete(f"summary:{widget_id}")
    cache.delete(f"detail:{widget_id}")
    return result
