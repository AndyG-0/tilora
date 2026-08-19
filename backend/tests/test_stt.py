from __future__ import annotations

import pytest

from app import stt
from app.stt import openai_stt


def test_openai_stt_is_configured():
    assert openai_stt.is_configured({}) is False
    assert openai_stt.is_configured({"openai_stt_enabled": ""}) is False
    assert openai_stt.is_configured({"openai_stt_enabled": "true"}) is False
    assert openai_stt.is_configured({"openai_api_key": "sk-test"}) is False
    assert openai_stt.is_configured({"openai_stt_enabled": "true", "openai_api_key": "sk-test"}) is True


def test_stt_is_available_and_active_provider():
    assert stt.is_stt_available({}) is False
    assert stt.get_active_provider({}) is None

    configured = {"openai_stt_enabled": "true", "openai_api_key": "sk-test"}
    assert stt.is_stt_available(configured) is True
    assert stt.get_active_provider(configured) == "openai"


@pytest.mark.asyncio
async def test_openai_stt_transcribe(monkeypatch):
    class FakeLitellm:
        @staticmethod
        async def atranscription(model, file, api_key, timeout):
            assert model == "openai/whisper-1"
            assert api_key == "sk-test"
            assert file.name == "sample.webm"
            return {"text": "hello world from whisper"}

    import sys

    monkeypatch.setitem(sys.modules, "litellm", FakeLitellm)

    settings = {"openai_stt_enabled": "true", "openai_api_key": "sk-test"}
    result = await stt.transcribe(b"fake-audio-bytes", filename="sample.webm", settings=settings)
    assert result == "hello world from whisper"


@pytest.mark.asyncio
async def test_stt_transcribe_raises_when_disabled():
    with pytest.raises(stt.STTError, match="No Speech-to-Text provider is enabled"):
        await stt.transcribe(b"fake-audio-bytes", settings={})
