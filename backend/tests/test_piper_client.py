from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.integrations import piper_client


@respx.mock
async def test_synthesize_posts_text_and_voice_and_returns_audio_bytes():
    route = respx.post("http://piper.local:5000/api/tts").mock(
        return_value=httpx.Response(200, content=b"RIFF....WAVEfmt ")
    )

    result = await piper_client.synthesize("http://piper.local:5000", "Hello there", "en_US-amy-medium")

    assert route.called
    assert json.loads(route.calls.last.request.content) == {"text": "Hello there", "voice": "en_US-amy-medium"}
    assert result == b"RIFF....WAVEfmt "


@respx.mock
async def test_synthesize_strips_trailing_slash_from_server_url():
    route = respx.post("http://piper.local:5000/api/tts").mock(return_value=httpx.Response(200, content=b"wav"))

    await piper_client.synthesize("http://piper.local:5000/", "Hi", "voice1")

    assert route.called


@respx.mock
async def test_synthesize_raises_on_non_200_response():
    respx.post("http://piper.local:5000/api/tts").mock(return_value=httpx.Response(500))

    with pytest.raises(piper_client.PiperError, match="HTTP 500"):
        await piper_client.synthesize("http://piper.local:5000", "Hi", "voice1")


@respx.mock
async def test_synthesize_raises_on_connection_error():
    respx.post("http://piper.local:5000/api/tts").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(piper_client.PiperError, match="Could not reach Piper server"):
        await piper_client.synthesize("http://piper.local:5000", "Hi", "voice1")
