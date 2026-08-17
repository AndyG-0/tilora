from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.ai import assistant
from app.ai.router import select_relevant_topics
from app.api.widgets import _widget_is_visible
from app.auth import get_current_device, get_current_user
from app.config import effective_settings, list_widget_configs, load_dashboard_config
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.alert.plugin import AlertPlugin
from app.plugins.base import Plugin, registry
from app.plugins.naming import display_names
from app.storage.db import hidden_widget_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# The frontend speaks this route's answer aloud via SpeechSynthesis
# immediately after showing it (see `+page.svelte`'s mic flow) — asking for
# plain spoken sentences up front avoids markdown/bullet formatting that
# reads badly through TTS.
_SPEECH_SYSTEM_PROMPT = (
    "Answer in 1-3 plain spoken sentences with no markdown, bullet points, or headings — "
    "your answer will be read aloud by a speech synthesizer."
)

# Matches litellm/OpenAI's "Please try again in 10.157s" wording so we can
# surface a concrete wait time even when the provider doesn't send a
# Retry-After header (litellm's RateLimitError only forwards headers when the
# vendor response set them -- see litellm.exceptions.RateLimitError).
_RETRY_AFTER_TEXT_PATTERN = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


def _rate_limit_retry_seconds(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            try:
                return max(1, round(float(retry_after)))
            except ValueError:
                pass
    match = _RETRY_AFTER_TEXT_PATTERN.search(str(exc))
    if match:
        return max(1, round(float(match.group(1))))
    return None


@router.post("/ask")
async def ask(
    payload: dict[str, str],
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="'text' is required")
    topic_plugins = await _visible_topic_plugins(user, device)
    names = display_names(topic_plugins)
    router_topics = [{"id": plugin.id, "name": names[plugin.id]} for plugin in topic_plugins]
    allowed_widget_ids = await select_relevant_topics(text, router_topics)
    try:
        result = await assistant.ask(
            text,
            system_prompt=_SPEECH_SYSTEM_PROMPT,
            user=user,
            device=device,
            allowed_widget_ids=allowed_widget_ids,
        )
    except Exception as exc:
        logger.exception("Assistant request failed")
        # litellm.RateLimitError (and openai's, which it subclasses) sets
        # status_code=429 -- checked by attribute rather than importing
        # litellm here, since app.ai.provider only imports it lazily to
        # avoid paying its ~1s import cost on every backend start.
        if getattr(exc, "status_code", None) == 429:
            retry_seconds = _rate_limit_retry_seconds(exc)
            detail = (
                f"The AI assistant is getting too many requests right now — try again in about "
                f"{retry_seconds} second{'s' if retry_seconds != 1 else ''}."
                if retry_seconds is not None
                else "The AI assistant is getting too many requests right now — try again in a moment."
            )
            raise HTTPException(status_code=429, detail=detail) from exc
        raise HTTPException(status_code=502, detail="The AI assistant is unavailable right now.") from exc
    return {"text": result.text, "action": result.navigation}


async def _visible_topic_plugins(user: dict[str, Any], device: dict[str, Any]) -> list[Plugin]:
    """Plugins that have AI tools and are visible to this (user, device).

    Shared by GET /topics (which lists them for display) and POST /ask
    (which lists them for the tool-selection router) so the two never drift
    on what counts as a "topic".
    """
    config = await asyncio.to_thread(load_dashboard_config)
    hidden = await asyncio.to_thread(hidden_widget_ids, user["id"], device["id"])
    visible_ids = {
        w["id"]
        for w in list_widget_configs(config)
        if w.get("enabled", True) and _widget_is_visible(w, user["id"], device["id"], hidden)
    }

    return [
        plugin
        for plugin in registry.all()
        if plugin.id in visible_ids
        and plugin.get_ai_tools()
        and not isinstance(plugin, AlertPlugin)
        and not isinstance(plugin, AIInsightsPlugin)
    ]


@router.get("/config")
async def config(
    user: dict[str, Any] = Depends(get_current_user),
):
    settings_dict = await asyncio.to_thread(effective_settings)
    agent_name = (settings_dict.get("ai_agent_name") or "").strip() or "Tilora"
    return {"agent_name": agent_name}


@router.get("/topics")
async def topics(
    user: dict[str, Any] = Depends(get_current_user),
    device: dict[str, Any] = Depends(get_current_device),
):
    topic_plugins = await _visible_topic_plugins(user, device)
    names = display_names(topic_plugins)
    return [{"id": plugin.id, "name": names[plugin.id]} for plugin in topic_plugins]
