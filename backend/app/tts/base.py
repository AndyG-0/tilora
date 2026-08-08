"""Shared types for the pluggable TTS provider layer (see app/tts/__init__.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TTSProvider = Literal["openai", "piper"]


@dataclass(frozen=True)
class VoiceInfo:
    id: str
    label: str
    provider: TTSProvider
