"""Asus Router test-connection route.

A dedicated router rather than folding into `widgets.py`, since it needs to
test not-yet-saved connection settings — same reasoning as
`app/api/pihole.py` / `app/api/synology.py`. Settings are read from the
*live* registered plugin instance (not `app.config.widget_config`, which
only reflects `dashboard.yaml` and misses DB-persisted overrides) so a
connection just saved from the widget's detail view can be tested
immediately.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.integrations import asus_router_client
from app.plugins.asus_router.plugin import AsusRouterPlugin
from app.plugins.base import registry

router = APIRouter(prefix="/api/asus-router", tags=["asus_router"])


def _get_plugin(widget_id: str) -> AsusRouterPlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, AsusRouterPlugin):
        raise HTTPException(status_code=404, detail=f"Unknown Asus Router widget '{widget_id}'")
    return plugin


@router.post("/{widget_id}/test-connection")
async def test_connection(widget_id: str, payload: dict[str, Any]):
    plugin = _get_plugin(widget_id)
    candidate_settings = {**plugin.config["settings"], **payload}
    try:
        product_id = await asus_router_client.test_connection(candidate_settings, widget_id)
    except asus_router_client.AsusRouterError as exc:
        return {"ok": False, "product_id": None, "error": str(exc)}
    return {"ok": True, "product_id": product_id, "error": None}
