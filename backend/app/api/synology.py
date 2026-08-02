"""Synology test-connection route.

A dedicated router rather than folding into `widgets.py`, since it needs to
test not-yet-saved connection settings — same reasoning as
`app/api/pihole.py`. Settings are read from the *live* registered plugin
instance (not `app.config.widget_config`, which only reflects
`dashboard.yaml` and misses DB-persisted overrides) so a connection just
saved from the widget's detail view can be tested immediately.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.integrations import synology_client
from app.plugins.base import registry
from app.plugins.synology.plugin import SynologyPlugin

router = APIRouter(prefix="/api/synology", tags=["synology"])


def _get_plugin(widget_id: str) -> SynologyPlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, SynologyPlugin):
        raise HTTPException(status_code=404, detail=f"Unknown Synology widget '{widget_id}'")
    return plugin


@router.post("/{widget_id}/test-connection")
async def test_connection(widget_id: str, payload: dict[str, Any]):
    plugin = _get_plugin(widget_id)
    candidate_settings = {**plugin.config["settings"], **payload}
    try:
        model = await synology_client.test_connection(candidate_settings, widget_id)
    except synology_client.SynologyError as exc:
        return {"ok": False, "model": None, "error": str(exc)}
    return {"ok": True, "model": model, "error": None}
