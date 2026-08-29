"""Aggregates every admin-enabled TTS provider behind one small interface.

Mirrors how app.ai.provider abstracts multiple LLM providers behind one call,
but for speech synthesis. Browser voices are NOT part of this module —
speechSynthesis is entirely client-side and never touches the backend; see
frontend/src/lib/speech.ts. This module only knows about cloud/self-hosted
providers an admin has explicitly enabled via effective_settings().
"""

from __future__ import annotations

from app.config import effective_settings
from app.tts import openai_tts, piper_tts
from app.tts.base import TTSProvider, VoiceInfo

__all__ = ["TTSError", "TTSProvider", "VoiceInfo", "list_available_voices", "synthesize"]

_PROVIDERS = {"openai": openai_tts, "piper": piper_tts}
_CONTENT_TYPE_BY_PROVIDER = {"openai": "audio/mpeg", "piper": "audio/wav"}


class TTSError(Exception):
    """Raised when a synthesize request names a disabled provider or unknown voice."""


async def list_available_voices() -> list[VoiceInfo]:
    settings = await effective_settings()
    voices: list[VoiceInfo] = []
    for module in _PROVIDERS.values():
        voices.extend(module.list_voices(settings))
    return voices


async def synthesize(provider: TTSProvider, voice_id: str, text: str) -> tuple[bytes, str]:
    """Returns (audio_bytes, content_type).

    Re-validates the provider is enabled and the voice_id is one it currently
    exposes, rather than trusting the frontend's earlier catalog fetch, since
    an admin could have disabled it between the two requests.
    """
    module = _PROVIDERS.get(provider)
    if module is None:
        raise TTSError(f"Unknown TTS provider '{provider}'")
    settings = await effective_settings()
    if not module.is_configured(settings):
        raise TTSError(f"TTS provider '{provider}' is not enabled")
    valid_ids = {v.id for v in module.list_voices(settings)}
    if voice_id not in valid_ids:
        raise TTSError(f"Unknown voice '{voice_id}' for provider '{provider}'")
    audio = await module.synthesize(text, voice_id, settings)
    return audio, _CONTENT_TYPE_BY_PROVIDER[provider]
