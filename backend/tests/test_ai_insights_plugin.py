from __future__ import annotations

from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.storage import db


def make_plugin() -> AIInsightsPlugin:
    return AIInsightsPlugin(
        {
            "id": "ai-insights",
            "settings": {
                "title": "Daily Briefing",
                "cron": "30 6 * * *",
                "prompt": "Say hello",
            },
        }
    )


async def test_get_summary_with_no_prior_run(tmp_db):
    plugin = make_plugin()
    summary = await plugin.get_summary()
    assert summary == {
        "title": "Daily Briefing",
        "text": "No briefing generated yet.",
        "ran_at": None,
    }


async def test_get_summary_returns_latest_run(tmp_db):
    plugin = make_plugin()
    db.record_ai_run(plugin.id, {"text": "It's sunny today."})

    summary = await plugin.get_summary()

    assert summary["title"] == "Daily Briefing"
    assert summary["text"] == "It's sunny today."
    assert summary["ran_at"] is not None


async def test_get_detail_includes_history(tmp_db):
    plugin = make_plugin()
    db.record_ai_run(plugin.id, {"text": "First run"})
    db.record_ai_run(plugin.id, {"text": "Second run"})

    detail = await plugin.get_detail()

    assert detail["text"] == "Second run"
    assert len(detail["history"]) == 2
    assert [h["text"] for h in detail["history"]] == ["Second run", "First run"]


async def test_get_detail_includes_prompt_and_cron(tmp_db):
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["prompt"] == "Say hello"
    assert detail["cron"] == "30 6 * * *"


async def test_get_detail_includes_topics(tmp_db):
    plugin = AIInsightsPlugin(
        {
            "id": "ai-insights",
            "settings": {"cron": "30 6 * * *", "prompt": "Say hello", "topics": ["calendar", "weather"]},
        }
    )

    detail = await plugin.get_detail()

    assert detail["topics"] == ["calendar", "weather"]


async def test_get_detail_defaults_topics_to_empty_list(tmp_db):
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["topics"] == []


async def test_prompt_and_cron_properties():
    plugin = make_plugin()
    assert plugin.prompt == "Say hello"
    assert plugin.cron == "30 6 * * *"


async def test_language_defaults_to_en():
    plugin = make_plugin()
    assert plugin.language == "en"


async def test_language_reads_from_settings():
    plugin = AIInsightsPlugin(
        {
            "id": "ai-insights",
            "settings": {"cron": "30 6 * * *", "prompt": "Say hello", "language": "es"},
        }
    )
    assert plugin.language == "es"


async def test_get_detail_includes_language(tmp_db):
    plugin = AIInsightsPlugin(
        {
            "id": "ai-insights",
            "settings": {"cron": "30 6 * * *", "prompt": "Say hello", "language": "fr"},
        }
    )

    detail = await plugin.get_detail()

    assert detail["language"] == "fr"


async def test_get_detail_defaults_language_to_en(tmp_db):
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["language"] == "en"
