"""OpenAI Whisper cloud speech-to-text, via litellm (litellm.atranscription).

Transcribes audio bytes recorded by the browser (WebM, OGG, WAV, MP4, etc.)
using the admin-configured OpenAI API key.
"""

from __future__ import annotations

import io
from typing import Any


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("openai_stt_enabled")) and bool(settings.get("openai_api_key"))


async def transcribe(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    settings: dict[str, Any],
) -> str:
    """Transcribe audio bytes using OpenAI Whisper.

    Imported lazily so backend startup isn't delayed if cloud STT is unused.
    """
    import litellm

    model = f"openai/{settings.get('openai_stt_model') or 'whisper-1'}"
    api_key = settings.get("openai_api_key")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename or "audio.webm"

    response = await litellm.atranscription(
        model=model,
        file=audio_file,
        api_key=api_key,
        timeout=30,
    )

    if isinstance(response, dict):
        return response.get("text", "")
    return getattr(response, "text", "") or ""
