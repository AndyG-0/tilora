from __future__ import annotations

import litellm
import pytest

from app import tts
from app.tts import openai_tts, piper_tts

_OPENAI_SETTINGS = {
    "openai_tts_enabled": "true",
    "openai_tts_model": "gpt-4o-mini-tts",
    "openai_api_key": "sk-openai",
}

_PIPER_SETTINGS = {
    "piper_tts_enabled": "true",
    "piper_server_url": "http://piper.local:5000",
    "piper_voices": "en_US-lessac-medium|Lessac,en_US-amy-medium",
}


# --- openai_tts.py ---


def test_openai_is_configured_requires_enabled_flag_and_api_key():
    assert openai_tts.is_configured(_OPENAI_SETTINGS) is True
    assert openai_tts.is_configured({**_OPENAI_SETTINGS, "openai_tts_enabled": ""}) is False
    assert openai_tts.is_configured({**_OPENAI_SETTINGS, "openai_api_key": None}) is False


def test_openai_list_voices_empty_when_not_configured():
    assert openai_tts.list_voices({"openai_tts_enabled": "", "openai_api_key": None}) == []


def test_openai_list_voices_returns_fixed_catalog_when_configured():
    voices = openai_tts.list_voices(_OPENAI_SETTINGS)

    assert len(voices) == 9
    assert all(v.provider == "openai" for v in voices)
    assert {v.id for v in voices} >= {"alloy", "nova", "onyx"}


async def test_openai_synthesize_calls_litellm_aspeech_with_expected_args(monkeypatch):
    captured = {}

    class FakeResponse:
        content = b"mp3-bytes"

    async def fake_aspeech(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(litellm, "aspeech", fake_aspeech)

    result = await openai_tts.synthesize("Hello", "nova", _OPENAI_SETTINGS)

    assert result == b"mp3-bytes"
    assert captured["model"] == "openai/gpt-4o-mini-tts"
    assert captured["input"] == "Hello"
    assert captured["voice"] == "nova"
    assert captured["api_key"] == "sk-openai"
    assert captured["response_format"] == "mp3"


async def test_openai_synthesize_falls_back_to_default_model_when_unset(monkeypatch):
    captured = {}

    class FakeResponse:
        content = b"mp3-bytes"

    async def fake_aspeech(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(litellm, "aspeech", fake_aspeech)

    await openai_tts.synthesize("Hi", "alloy", {**_OPENAI_SETTINGS, "openai_tts_model": None})

    assert captured["model"] == "openai/gpt-4o-mini-tts"


# --- piper_tts.py ---


def test_piper_is_configured_requires_enabled_url_and_voices():
    assert piper_tts.is_configured(_PIPER_SETTINGS) is True
    assert piper_tts.is_configured({**_PIPER_SETTINGS, "piper_tts_enabled": ""}) is False
    assert piper_tts.is_configured({**_PIPER_SETTINGS, "piper_server_url": None}) is False
    assert piper_tts.is_configured({**_PIPER_SETTINGS, "piper_voices": None}) is False


def test_piper_parse_voices_handles_bare_id_and_labeled_entries():
    voices = piper_tts._parse_voices("en_US-lessac-medium|Lessac,en_US-amy-medium")

    assert voices[0].id == "en_US-lessac-medium"
    assert voices[0].label == "Lessac"
    assert voices[0].provider == "piper"
    assert voices[1].id == "en_US-amy-medium"
    assert voices[1].label == "En Us Amy Medium"


def test_piper_parse_voices_skips_blank_entries():
    voices = piper_tts._parse_voices("en_US-amy-medium, ,")

    assert len(voices) == 1
    assert voices[0].id == "en_US-amy-medium"


def test_piper_list_voices_empty_when_not_configured():
    assert piper_tts.list_voices({"piper_tts_enabled": "", "piper_server_url": None, "piper_voices": None}) == []


def test_piper_list_voices_returns_parsed_entries_when_configured():
    voices = piper_tts.list_voices(_PIPER_SETTINGS)

    assert [v.id for v in voices] == ["en_US-lessac-medium", "en_US-amy-medium"]


async def test_piper_synthesize_delegates_to_piper_client(monkeypatch):
    captured = {}

    async def fake_synthesize(server_url, text, voice_id):
        captured.update(server_url=server_url, text=text, voice_id=voice_id)
        return b"wav-bytes"

    monkeypatch.setattr("app.tts.piper_tts.piper_client.synthesize", fake_synthesize)

    result = await piper_tts.synthesize("Hello", "en_US-amy-medium", _PIPER_SETTINGS)

    assert result == b"wav-bytes"
    assert captured == {
        "server_url": "http://piper.local:5000",
        "text": "Hello",
        "voice_id": "en_US-amy-medium",
    }


# --- app/tts/__init__.py aggregator ---


def test_list_available_voices_merges_every_enabled_provider(monkeypatch):
    monkeypatch.setattr(tts, "effective_settings", lambda: {**_OPENAI_SETTINGS, **_PIPER_SETTINGS})

    voices = tts.list_available_voices()

    providers = {v.provider for v in voices}
    assert providers == {"openai", "piper"}


def test_list_available_voices_empty_when_nothing_enabled(monkeypatch):
    monkeypatch.setattr(tts, "effective_settings", lambda: {})

    assert tts.list_available_voices() == []


async def test_synthesize_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(tts, "effective_settings", lambda: {})

    with pytest.raises(tts.TTSError, match="Unknown TTS provider"):
        await tts.synthesize("bogus", "voice", "hi")  # type: ignore[arg-type]


async def test_synthesize_raises_when_provider_not_enabled(monkeypatch):
    monkeypatch.setattr(tts, "effective_settings", lambda: {"openai_tts_enabled": "", "openai_api_key": None})

    with pytest.raises(tts.TTSError, match="not enabled"):
        await tts.synthesize("openai", "nova", "hi")


async def test_synthesize_raises_for_unknown_voice_id(monkeypatch):
    monkeypatch.setattr(tts, "effective_settings", lambda: _OPENAI_SETTINGS)

    with pytest.raises(tts.TTSError, match="Unknown voice"):
        await tts.synthesize("openai", "not-a-real-voice", "hi")


async def test_synthesize_returns_audio_and_content_type(monkeypatch):
    monkeypatch.setattr(tts, "effective_settings", lambda: _OPENAI_SETTINGS)

    async def fake_synthesize(text, voice_id, settings):
        return b"audio-bytes"

    monkeypatch.setattr(tts.openai_tts, "synthesize", fake_synthesize)

    audio, content_type = await tts.synthesize("openai", "nova", "hi")

    assert audio == b"audio-bytes"
    assert content_type == "audio/mpeg"
