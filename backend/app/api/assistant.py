from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.ai import assistant
from app.auth import get_current_device, get_current_user
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.alert.plugin import AlertPlugin
from app.plugins.base import registry

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
async def topics():
    # The same catalog voice control draws its tools from (registry.all_tools
    # via app.ai.assistant.ask), minus AlertPlugin (its one tool, create_alert,
    # is a write action rather than something to "cover" in a summary) and
    # AIInsightsPlugin instances (a summary widget can't reference itself).
    return [
        {"id": plugin.id, "name": plugin.name}
        for plugin in registry.all()
        if plugin.get_ai_tools() and not isinstance(plugin, AlertPlugin) and not isinstance(plugin, AIInsightsPlugin)
    ]
