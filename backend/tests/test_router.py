from __future__ import annotations

from types import SimpleNamespace

import litellm

from app.ai import router

TOPICS = [{"id": "weather", "name": "Weather"}, {"id": "mapping", "name": "Mapping"}]


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


async def test_select_relevant_topics_returns_none_when_no_topics_given(monkeypatch):
    called = False

    async def fake_acompletion(**kwargs):
        nonlocal called
        called = True
        return _fake_response("[]")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("what's the weather?", [])

    assert result is None
    assert called is False


async def test_select_relevant_topics_returns_matching_ids(monkeypatch):
    async def fake_acompletion(**kwargs):
        return _fake_response('["weather"]')

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("what's the weather?", TOPICS)

    assert result == ["weather"]


async def test_select_relevant_topics_filters_hallucinated_ids(monkeypatch):
    async def fake_acompletion(**kwargs):
        return _fake_response('["weather", "not-a-real-topic"]')

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("what's the weather?", TOPICS)

    assert result == ["weather"]


async def test_select_relevant_topics_returns_none_for_empty_selection(monkeypatch):
    async def fake_acompletion(**kwargs):
        return _fake_response("[]")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("what's the meaning of life?", TOPICS)

    assert result is None


async def test_select_relevant_topics_tolerates_markdown_fenced_response(monkeypatch):
    async def fake_acompletion(**kwargs):
        return _fake_response('Sure, here you go:\n```json\n["mapping"]\n```')

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("directions to taco bell", TOPICS)

    assert result == ["mapping"]


async def test_select_relevant_topics_returns_none_on_malformed_response(monkeypatch):
    async def fake_acompletion(**kwargs):
        return _fake_response("not json at all")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("what's the weather?", TOPICS)

    assert result is None


async def test_select_relevant_topics_returns_none_on_call_failure(monkeypatch):
    async def fake_acompletion(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    result = await router.select_relevant_topics("what's the weather?", TOPICS)

    assert result is None
