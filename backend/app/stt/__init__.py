"""Aggregates admin-enabled STT (Speech-to-Text) providers.

Mirrors app.tts for speech synthesis, providing transcription for browser
clients that cannot run native Web Speech API (e.g. open-source Chromium on
Raspberry Pi / Mac, Mozilla Firefox, Brave).
"""

from __future__ import annotations

from typing import Any

from app.config import effective_settings
from app.stt import openai_stt

__all__ = ["STTError", "is_stt_available", "transcribe"]

_PROVIDERS = {"openai": openai_stt}


class STTError(Exception):
    """Raised when transcription fails or no STT provider is configured."""


def is_stt_available(settings: dict[str, Any]) -> bool:
    return any(module.is_configured(settings) for module in _PROVIDERS.values())


def get_active_provider(settings: dict[str, Any]) -> str | None:
    for name, module in _PROVIDERS.items():
        if module.is_configured(settings):
            return name
    return None


async def transcribe(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    content_type: str = "audio/webm",
    settings: dict[str, Any] | None = None,
) -> str:
    """Transcribe audio bytes to text using the configured STT provider."""
    s = settings if settings is not None else await effective_settings()
    for name, module in _PROVIDERS.items():
        if module.is_configured(s):
            try:
                return await module.transcribe(audio_bytes, filename, content_type, s)
            except Exception as exc:
                raise STTError(f"STT transcription with '{name}' failed: {exc}") from exc

    raise STTError("No Speech-to-Text provider is enabled.")
