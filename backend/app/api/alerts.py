from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.storage import db
from app.storage.cache import cache

router = APIRouter(prefix="/api/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


def _invalidate(widget_id: str) -> None:
    cache.delete(f"summary:{widget_id}")
    cache.delete(f"detail:{widget_id}")


@router.post("")
async def create_alert(payload: dict[str, Any]):
    widget_id = payload.get("widget_id", "alert")
    alert = await asyncio.to_thread(
        db.create_alert,
        widget_id,
        payload["message"],
        payload.get("severity", "info"),
        payload.get("expires_in_minutes"),
    )
    _invalidate(widget_id)
    return alert


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(alert_id: int):
    alert = await asyncio.to_thread(db.get_alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Unknown alert '{alert_id}'")

    await asyncio.to_thread(db.dismiss_alert, alert_id)
    _invalidate(alert["widget_id"])
    return {"status": "ok"}
