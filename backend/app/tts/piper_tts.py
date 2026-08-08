"""Self-hosted Piper TTS, via app/integrations/piper_client.py."""

from __future__ import annotations

from typing import Any

from app.integrations import piper_client
from app.tts.base import VoiceInfo


def is_configured(settings: dict[str, Any]) -> bool:
    return (
        bool(settings.get("piper_tts_enabled"))
        and bool(settings.get("piper_server_url"))
        and bool(settings.get("piper_voices"))
    )


def _parse_voices(raw: str) -> list[VoiceInfo]:
    """Parses the admin-entered "id|Label,id2|Label2" (or bare "id,id2") string.

    A missing "|Label" falls back to a prettified id (underscores/dashes ->
    spaces, title-cased) so a minimal admin entry like "en_US-amy-medium"
    still shows something readable in the picker.
    """
    voices = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        voice_id, _, label = entry.partition("|")
        label = label.strip() or voice_id.replace("_", " ").replace("-", " ").title()
        voices.append(VoiceInfo(id=voice_id, label=label, provider="piper"))
    return voices


def list_voices(settings: dict[str, Any]) -> list[VoiceInfo]:
    if not is_configured(settings):
        return []
    return _parse_voices(settings["piper_voices"])


async def synthesize(text: str, voice_id: str, settings: dict[str, Any]) -> bytes:
    return await piper_client.synthesize(settings["piper_server_url"], text, voice_id)
