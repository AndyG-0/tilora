from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.auth import get_current_admin
from app.config import APP_SETTINGS_KEYS, effective_settings
from app.storage.cache import cache
from app.storage.db import save_app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(get_current_admin)])

_SECRET_KEYS = (
    "anthropic_api_key",
    "openai_api_key",
    "gemini_api_key",
    "google_calendar_client_id",
    "google_calendar_client_secret",
    "microsoft_calendar_client_id",
    "microsoft_calendar_client_secret",
    "caldav_password",
    "icloud_password",
)
# Not secret, but user-editable app settings that aren't ai_model/timezone —
# returned as-is (unlike _SECRET_KEYS, which only expose a `has_<key>` flag)
# so the user can see/edit them without retyping.
_PLAIN_KEYS = ("ai_reasoning_effort", "caldav_url", "caldav_username", "icloud_username")
# Widgets whose summary/detail is derived entirely from global app settings
# (not their own per-widget settings) — their cache must be invalidated
# whenever those settings change, or they'd keep serving a stale value for
# up to `refresh_interval_seconds`.
_GLOBAL_SETTINGS_WIDGET_IDS = ("clock", "date")


class UpdateSettingsRequest(BaseModel):
    # `extra="forbid"` doubles as the allow-list: a key outside APP_SETTINGS_KEYS
    # is rejected with a 422 instead of being silently persisted.
    model_config = ConfigDict(extra="forbid")

    ai_model: str | None = None
    ai_reasoning_effort: str | None = None
    timezone: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    google_calendar_client_id: str | None = None
    google_calendar_client_secret: str | None = None
    microsoft_calendar_client_id: str | None = None
    microsoft_calendar_client_secret: str | None = None
    caldav_url: str | None = None
    caldav_username: str | None = None
    caldav_password: str | None = None
    icloud_username: str | None = None
    icloud_password: str | None = None


assert set(UpdateSettingsRequest.model_fields) == set(APP_SETTINGS_KEYS), (
    "UpdateSettingsRequest fields must mirror APP_SETTINGS_KEYS exactly"
)


def _public_shape(current: dict[str, Any]) -> dict[str, Any]:
    # Secrets are write-only: callers get a boolean "is it set", never the
    # raw value, so the key can't leak back out over the API.
    return {
        "ai_model": current["ai_model"],
        "timezone": current["timezone"],
        **{key: current.get(key) or "" for key in _PLAIN_KEYS},
        **{f"has_{key}": bool(current.get(key)) for key in _SECRET_KEYS},
    }


@router.get("")
async def get_settings():
    return _public_shape(effective_settings())


@router.patch("")
async def update_settings(payload: UpdateSettingsRequest):
    # An empty string means "clear this key"; `save_app_settings` deletes
    # the override for any key mapped to None, falling back to the .env
    # default (or unset) on the next read. `exclude_unset` keeps this a
    # partial update — a key the client never sent stays untouched.
    overrides = {key: (value if value != "" else None) for key, value in payload.model_dump(exclude_unset=True).items()}
    await asyncio.to_thread(save_app_settings, overrides)
    for widget_id in _GLOBAL_SETTINGS_WIDGET_IDS:
        cache.delete(f"summary:{widget_id}")
        cache.delete(f"detail:{widget_id}")
    return _public_shape(effective_settings())
