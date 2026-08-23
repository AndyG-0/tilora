from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import artificial_analysis_client

_URL = "https://artificialanalysis.ai/api/v2/language/models/free"


def _raw_model(model_id: str, name: str, coding_index: float = 50.0) -> dict:
    return {
        "id": model_id,
        "name": name,
        "slug": name.lower(),
        "release_date": "2026-01-01",
        "model_creator": {"id": "acme", "name": "Acme"},
        "evaluations": {
            "artificial_analysis_intelligence_index": 60.0,
            "artificial_analysis_coding_index": coding_index,
            "artificial_analysis_agentic_index": 40.0,
        },
        "pricing": {
            "price_1m_input_tokens": 1.0,
            "price_1m_output_tokens": 5.0,
            "price_1m_cache_hit_tokens": 0.5,
            "price_1m_cache_write_tokens": 1.5,
        },
        "performance": {
            "median_output_tokens_per_second": 80.0,
            "median_time_to_first_token_seconds": 0.4,
            "median_time_to_first_answer_token_seconds": 0.5,
            "median_end_to_end_response_time_seconds": 3.0,
        },
    }


def _page(models: list[dict], has_more: bool = False) -> dict:
    return {
        "tier": "free",
        "intelligence_index_version": "1",
        "pagination": {"page": 1, "page_size": 50, "total_pages": 1, "has_more": has_more},
        "data": models,
    }


@respx.mock
async def test_get_language_models_flattens_fields():
    respx.get(_URL).mock(return_value=httpx.Response(200, json=_page([_raw_model("m1", "Model One")])))

    models = await artificial_analysis_client.get_language_models("test-key")

    assert models == [
        {
            "id": "m1",
            "name": "Model One",
            "slug": "model one",
            "release_date": "2026-01-01",
            "creator": "Acme",
            "intelligence_index": 60.0,
            "coding_index": 50.0,
            "agentic_index": 40.0,
            "price_input_per_1m": 1.0,
            "price_output_per_1m": 5.0,
            "price_cache_hit_per_1m": 0.5,
            "price_cache_write_per_1m": 1.5,
            "blended_price_per_1m": (3 * 1.0 + 5.0) / 4,
            "output_tokens_per_second": 80.0,
            "time_to_first_token_seconds": 0.4,
            "time_to_first_answer_token_seconds": 0.5,
            "end_to_end_response_time_seconds": 3.0,
        }
    ]


@respx.mock
async def test_get_language_models_sends_the_api_key_header():
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_page([])))

    await artificial_analysis_client.get_language_models("my-key")

    assert route.calls.last.request.headers["x-api-key"] == "my-key"


@respx.mock
async def test_get_language_models_pages_until_has_more_is_false():
    route = respx.get(_URL).mock(
        side_effect=[
            httpx.Response(200, json=_page([_raw_model("m1", "Model One")], has_more=True)),
            httpx.Response(200, json=_page([_raw_model("m2", "Model Two")], has_more=False)),
        ]
    )

    models = await artificial_analysis_client.get_language_models("test-key")

    assert [m["id"] for m in models] == ["m1", "m2"]
    assert route.call_count == 2


@respx.mock
async def test_get_language_models_stops_at_the_page_safety_cap(monkeypatch):
    monkeypatch.setattr(artificial_analysis_client, "_MAX_PAGES", 3)
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_page([_raw_model("m", "M")], has_more=True)))

    models = await artificial_analysis_client.get_language_models("test-key")

    assert route.call_count == 3
    assert len(models) == 3


async def test_get_language_models_raises_immediately_without_a_key():
    with pytest.raises(artificial_analysis_client.ArtificialAnalysisError):
        await artificial_analysis_client.get_language_models(None)


async def test_get_language_models_raises_immediately_with_an_empty_key():
    with pytest.raises(artificial_analysis_client.ArtificialAnalysisError):
        await artificial_analysis_client.get_language_models("")


@respx.mock
async def test_get_language_models_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(artificial_analysis_client, "_RETRY_BACKOFF_SECONDS", 0)
    respx.get(_URL).mock(return_value=httpx.Response(401, json={"error": {"message": "invalid api key"}}))

    with pytest.raises(artificial_analysis_client.ArtificialAnalysisError, match="invalid api key"):
        await artificial_analysis_client.get_language_models("bad-key")


@respx.mock
async def test_get_language_models_retries_once_on_a_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr(artificial_analysis_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get(_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=_page([_raw_model("m1", "Model One")]))]
    )

    models = await artificial_analysis_client.get_language_models("test-key")

    assert len(models) == 1
    assert route.call_count == 2


@respx.mock
async def test_get_language_models_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(artificial_analysis_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get(_URL).mock(return_value=httpx.Response(503))

    with pytest.raises(artificial_analysis_client.ArtificialAnalysisError):
        await artificial_analysis_client.get_language_models("test-key")

    assert route.call_count == artificial_analysis_client._MAX_ATTEMPTS


def test_is_configured():
    assert artificial_analysis_client.is_configured("a-key") is True
    assert artificial_analysis_client.is_configured("") is False
    assert artificial_analysis_client.is_configured(None) is False
