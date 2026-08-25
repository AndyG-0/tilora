"""Voice-catalog and synthesis routes for cloud/self-hosted TTS.

Browser voices aren't served here — they're purely client-side (see
frontend/src/lib/speech.ts). Any logged-in user (not just admins) may call
these: an admin controls *which* providers/voices exist at all (app/config.py
+ app/api/settings.py), but any household member picks their own voice from
whatever's on offer, same tier as app/api/screensaver.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.tts import TTSError, TTSProvider, list_available_voices, synthesize

router = APIRouter(prefix="/api/tts", tags=["tts"])

# Bounds a synthesize request to roughly what the voice assistant / read-aloud
# button ever sends (a few spoken sentences — see
# app/api/assistant.py's _SPEECH_SYSTEM_PROMPT), so a stray huge payload can't
# balloon cloud TTS cost or a self-hosted server's synth time.
_MAX_TEXT_LENGTH = 1000


class SynthesizeRequest(BaseModel):
    provider: TTSProvider
    voice_id: str
    text: str = Field(min_length=1, max_length=_MAX_TEXT_LENGTH)


@router.get("/voices")
async def voices(user: dict[str, Any] = Depends(get_current_user)):
    return [{"id": v.id, "label": v.label, "provider": v.provider} for v in await list_available_voices()]


@router.post("/synthesize")
async def synthesize_route(payload: SynthesizeRequest, user: dict[str, Any] = Depends(get_current_user)):
    try:
        audio, content_type = await synthesize(payload.provider, payload.voice_id, payload.text)
    except TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=audio, media_type=content_type)
