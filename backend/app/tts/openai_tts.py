"""OpenAI cloud text-to-speech, via litellm's speech passthrough (litellm.aspeech).

OpenAI's TTS voices are a small, fixed, publicly documented catalog — not
account-specific like Piper's admin-installed models — so they're hardcoded
here rather than admin-configured; there's nothing to list per-account.
"""

from __future__ import annotations

from typing import Any

from app.tts.base import VoiceInfo

_VOICES: tuple[VoiceInfo, ...] = (
    VoiceInfo(id="alloy", label="Alloy", provider="openai"),
    VoiceInfo(id="ash", label="Ash", provider="openai"),
    VoiceInfo(id="coral", label="Coral", provider="openai"),
    VoiceInfo(id="echo", label="Echo", provider="openai"),
    VoiceInfo(id="fable", label="Fable", provider="openai"),
    VoiceInfo(id="nova", label="Nova", provider="openai"),
    VoiceInfo(id="onyx", label="Onyx", provider="openai"),
    VoiceInfo(id="sage", label="Sage", provider="openai"),
    VoiceInfo(id="shimmer", label="Shimmer", provider="openai"),
)


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("openai_tts_enabled")) and bool(settings.get("openai_api_key"))


def list_voices(settings: dict[str, Any]) -> list[VoiceInfo]:
    return list(_VOICES) if is_configured(settings) else []


async def synthesize(text: str, voice_id: str, settings: dict[str, Any]) -> bytes:
    # Imported lazily, same rationale as AIProvider.run_prompt: litellm pulls
    # in the openai SDK/tiktoken/tokenizers, so a backend that never uses
    # cloud TTS shouldn't pay that import cost at every startup.
    import litellm

    model = f"openai/{settings.get('openai_tts_model') or 'gpt-4o-mini-tts'}"
    response = await litellm.aspeech(
        model=model,
        input=text,
        voice=voice_id,
        api_key=settings.get("openai_api_key"),
        response_format="mp3",
        timeout=30,
    )
    return response.content
