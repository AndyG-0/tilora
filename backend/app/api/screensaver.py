from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_device, get_current_user
from app.storage.db import get_screensaver_settings, save_screensaver_settings

router = APIRouter(prefix="/api/screensaver", tags=["screensaver"])


class UpdateScreensaverSettingsRequest(BaseModel):
    enabled: bool | None = None
    idle_timeout_seconds: int | None = None
    rotation_interval_seconds: int | None = None
    widget_ids: list[str] | None = None
    text_animation_style: Literal["marquee", "matrix", "flipboard", "led_dots"] | None = None
    led_color: str | None = None
    text_pause_seconds: int | None = None
    flipboard_pattern: Literal["top_to_bottom", "random"] | None = None


@router.get("/settings")
async def get_settings(
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    return await asyncio.to_thread(get_screensaver_settings, user["id"], device["id"])


@router.patch("/settings")
async def update_settings(
    payload: UpdateScreensaverSettingsRequest,
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    overrides = payload.model_dump(exclude_unset=True)
    return await asyncio.to_thread(save_screensaver_settings, user["id"], device["id"], overrides)
