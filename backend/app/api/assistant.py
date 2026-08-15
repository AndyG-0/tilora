from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.ai import assistant
from app.api.widgets import _widget_is_visible
from app.auth import get_current_device, get_current_user
from app.config import list_widget_configs, load_dashboard_config
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.alert.plugin import AlertPlugin
from app.plugins.base import registry
from app.plugins.naming import display_names
from app.storage.db import hidden_widget_ids

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# The frontend speaks this route's answer aloud via SpeechSynthesis
# immediately after showing it (see `+page.svelte`'s mic flow) — asking for
# plain spoken sentences up front avoids markdown/bullet formatting that
# reads badly through TTS.
_SPEECH_SYSTEM_PROMPT = (
    "Answer in 1-3 plain spoken sentences with no markdown, bullet points, or headings — "
    "your answer will be read aloud by a speech synthesizer."
)


@router.post("/ask")
async def ask(
    payload: dict[str, str],
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="'text' is required")
    reply = await assistant.ask(text, system_prompt=_SPEECH_SYSTEM_PROMPT, user=user, device=device)
    return {"text": reply}


@router.get("/topics")
async def topics(
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    # Filter to plugins that have AI tools and are visible to this (user, device).
    config = await asyncio.to_thread(load_dashboard_config)
    hidden = await asyncio.to_thread(hidden_widget_ids, user["id"], device["id"])
    visible_ids = {
        w["id"]
        for w in list_widget_configs(config)
        if w.get("enabled", True) and _widget_is_visible(w, user["id"], device["id"], hidden)
    }

    topic_plugins = [
        plugin
        for plugin in registry.all()
        if plugin.id in visible_ids
        and plugin.get_ai_tools()
        and not isinstance(plugin, AlertPlugin)
        and not isinstance(plugin, AIInsightsPlugin)
    ]
    names = display_names(topic_plugins)
    return [{"id": plugin.id, "name": names[plugin.id]} for plugin in topic_plugins]
