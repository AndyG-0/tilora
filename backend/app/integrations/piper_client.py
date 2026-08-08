"""HTTP client for a self-hosted Piper (https://github.com/rhasspy/piper) TTS server.

ASSUMPTION FLAGGED FOR REVIEW: Piper has no single official multi-voice HTTP
contract. Stock `python -m piper.http_server` loads exactly one model at
startup and has no per-request voice selector, which doesn't fit "one server
URL + a list of voices" from the admin settings UI. This client instead
targets the shape used by common community wrappers: `POST {server_url}/api/tts`
with a JSON body `{"text": ..., "voice": ...}`, returning raw WAV bytes. If
the admin's actual Piper server differs, adjust `synthesize()` below to match
its real contract before relying on this in production.
"""

from __future__ import annotations

import httpx

_REQUEST_TIMEOUT_SECONDS = 30


class PiperError(Exception):
    """Raised when the configured Piper server is unreachable or errors out."""


async def synthesize(server_url: str, text: str, voice_id: str) -> bytes:
    url = server_url.rstrip("/") + "/api/tts"
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(url, json={"text": text, "voice": voice_id})
        except httpx.HTTPError as exc:
            raise PiperError(f"Could not reach Piper server at {server_url}: {exc}") from exc
    if response.status_code != 200:
        raise PiperError(f"Piper server returned HTTP {response.status_code}")
    return response.content
