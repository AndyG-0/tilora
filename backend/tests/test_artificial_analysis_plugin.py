from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.config import settings
from app.integrations import artificial_analysis_client
from app.plugins.artificial_analysis.plugin import ArtificialAnalysisPlugin
from app.storage import db

_URL = "https://artificialanalysis.ai/api/v2/language/models/free"


def _raw_model(model_id: str, name: str, *, coding=50.0, intelligence=60.0, output_price=5.0, tok_s=80.0) -> dict:
    return {
        "id": model_id,
        "name": name,
        "slug": name.lower(),
        "release_date": "2026-01-01",
        "model_creator": {"id": "acme", "name": "Acme"},
        "evaluations": {
            "artificial_analysis_intelligence_index": intelligence,
            "artificial_analysis_coding_index": coding,
            "artificial_analysis_agentic_index": 40.0,
        },
        "pricing": {
            "price_1m_input_tokens": 1.0,
            "price_1m_output_tokens": output_price,
            "price_1m_cache_hit_tokens": 0.5,
            "price_1m_cache_write_tokens": 1.5,
        },
        "performance": {
            "median_output_tokens_per_second": tok_s,
            "median_time_to_first_token_seconds": 0.4,
            "median_time_to_first_answer_token_seconds": 0.5,
            "median_end_to_end_response_time_seconds": 3.0,
        },
    }


def _page(models: list[dict]) -> dict:
    return {
        "tier": "free",
        "intelligence_index_version": "1",
        "pagination": {"page": 1, "page_size": 50, "total_pages": 1, "has_more": False},
        "data": models,
    }


def make_plugin(widget_id: str = "artificial_analysis", **plugin_settings) -> ArtificialAnalysisPlugin:
    return ArtificialAnalysisPlugin({"id": widget_id, "settings": plugin_settings})


def _flattened_model(model_id: str, name: str, **kwargs) -> dict:
    """A persisted-shape model, i.e. what `_flatten_model` produces — this is
    the shape actually stored in `artificial_analysis_fetches.result`, not
    the raw API response shape."""
    return artificial_analysis_client._flatten_model(_raw_model(model_id, name, **kwargs))  # noqa: SLF001


async def test_get_summary_not_configured_without_a_key(tmp_db):
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {"configured": False, "category": "coding", "models": []}


@respx.mock
async def test_get_summary_fetches_and_ranks_by_coding_index_by_default(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _raw_model("m1", "Low Coder", coding=10.0),
                    _raw_model("m2", "High Coder", coding=90.0),
                ]
            ),
        )
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["category"] == "coding"
    assert summary["stale"] is False
    assert [m["id"] for m in summary["models"]] == ["m2", "m1"]


@respx.mock
async def test_get_summary_slices_to_the_top_five(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    models = [_raw_model(f"m{i}", f"Model {i}", coding=float(i)) for i in range(10)]
    respx.get(_URL).mock(return_value=httpx.Response(200, json=_page(models)))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert len(summary["models"]) == 5
    assert summary["models"][0]["id"] == "m9"


@respx.mock
async def test_get_detail_returns_the_full_ranked_list(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    models = [_raw_model(f"m{i}", f"Model {i}", coding=float(i)) for i in range(10)]
    respx.get(_URL).mock(return_value=httpx.Response(200, json=_page(models)))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert len(detail["models"]) == 10
    assert detail["models"][0]["id"] == "m9"


@respx.mock
async def test_ranking_by_intelligence(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _raw_model("m1", "Model 1", intelligence=10.0),
                    _raw_model("m2", "Model 2", intelligence=90.0),
                ]
            ),
        )
    )
    plugin = make_plugin(category="intelligence")

    summary = await plugin.get_summary()

    assert [m["id"] for m in summary["models"]] == ["m2", "m1"]


@respx.mock
async def test_ranking_by_cost_is_cheapest_first(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _raw_model("expensive", "Expensive", output_price=100.0),
                    _raw_model("cheap", "Cheap", output_price=1.0),
                ]
            ),
        )
    )
    plugin = make_plugin(category="cost")

    summary = await plugin.get_summary()

    assert [m["id"] for m in summary["models"]] == ["cheap", "expensive"]


@respx.mock
async def test_ranking_by_speed_is_fastest_first(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _raw_model("slow", "Slow", tok_s=10.0),
                    _raw_model("fast", "Fast", tok_s=200.0),
                ]
            ),
        )
    )
    plugin = make_plugin(category="speed")

    summary = await plugin.get_summary()

    assert [m["id"] for m in summary["models"]] == ["fast", "slow"]


@respx.mock
async def test_second_call_within_24h_makes_no_additional_http_requests(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_page([_raw_model("m1", "Model 1")])))
    plugin = make_plugin()

    first = await plugin.get_summary()
    second = await plugin.get_summary()

    assert route.call_count == 1
    assert first["stale"] is False
    assert second["stale"] is False
    assert second["models"] == first["models"]


@respx.mock
async def test_refetches_after_24_hours(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    stale_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    db.record_artificial_analysis_fetch("global", {"models": [_flattened_model("old", "Old Model")]})
    # Backdate the persisted row past the 24h window directly via the db module.
    with db._connect() as conn:  # noqa: SLF001 - test needs to backdate fetched_at
        conn.execute("UPDATE artificial_analysis_fetches SET fetched_at = ?", (stale_time,))
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_page([_raw_model("new", "New Model")])))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert route.call_count == 1
    assert summary["models"][0]["id"] == "new"


@respx.mock
async def test_falls_back_to_stale_data_on_api_failure(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    monkeypatch.setattr(artificial_analysis_client, "_RETRY_BACKOFF_SECONDS", 0)
    stale_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    db.record_artificial_analysis_fetch("global", {"models": [_flattened_model("old", "Old Model")]})
    with db._connect() as conn:  # noqa: SLF001
        conn.execute("UPDATE artificial_analysis_fetches SET fetched_at = ?", (stale_time,))
    respx.get(_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["stale"] is True
    assert summary["models"][0]["id"] == "old"


@respx.mock
async def test_returns_empty_when_never_fetched_and_api_is_down(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    monkeypatch.setattr(artificial_analysis_client, "_RETRY_BACKOFF_SECONDS", 0)
    respx.get(_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {"configured": True, "category": "coding", "stale": False, "models": []}


def test_validate_settings_rejects_an_unknown_category(tmp_db):
    plugin = make_plugin()

    with pytest.raises(ValueError, match="category"):
        plugin.validate_settings({"category": "not-a-real-category"})


def test_validate_settings_accepts_a_known_category(tmp_db):
    plugin = make_plugin()

    plugin.validate_settings({"category": "speed"})


@respx.mock
async def test_ai_tools_reuse_the_gated_fetch_without_extra_http_calls(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    route = respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [
                    _raw_model("m1", "Model 1", coding=10.0, intelligence=90.0, output_price=1.0, tok_s=200.0),
                    _raw_model("m2", "Model 2", coding=90.0, intelligence=10.0, output_price=100.0, tok_s=10.0),
                ]
            ),
        )
    )
    plugin = make_plugin()
    tools = {tool.name: tool for tool in plugin.get_ai_tools()}
    assert set(tools) == {
        "get_best_coding_ai_models",
        "get_smartest_ai_models",
        "get_cheapest_ai_models",
        "get_fastest_ai_models",
    }

    coding = await tools["get_best_coding_ai_models"].handler()
    smartest = await tools["get_smartest_ai_models"].handler()
    cheapest = await tools["get_cheapest_ai_models"].handler()
    fastest = await tools["get_fastest_ai_models"].handler()

    assert coding["models"][0]["id"] == "m2"
    assert smartest["models"][0]["id"] == "m1"
    assert cheapest["models"][0]["id"] == "m1"
    assert fastest["models"][0]["id"] == "m1"
    # Four tool calls, but the underlying API is only hit once thanks to the
    # shared 24h-gated _fetch() — this is the direct proof that an AI tool
    # call never burns extra budget beyond the daily gate.
    assert route.call_count == 1


async def test_ai_tools_report_not_configured_without_a_key(tmp_db):
    plugin = make_plugin()
    tools = {tool.name: tool for tool in plugin.get_ai_tools()}

    result = await tools["get_best_coding_ai_models"].handler()

    assert result == {"models": [], "configured": False}


@respx.mock
async def test_ai_tools_respect_the_limit_parameter(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "artificial_analysis_api_key", "test-key")
    models = [_raw_model(f"m{i}", f"Model {i}", coding=float(i)) for i in range(10)]
    respx.get(_URL).mock(return_value=httpx.Response(200, json=_page(models)))
    plugin = make_plugin()
    tools = {tool.name: tool for tool in plugin.get_ai_tools()}

    result = await tools["get_best_coding_ai_models"].handler(limit=3)

    assert len(result["models"]) == 3
