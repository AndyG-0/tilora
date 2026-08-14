from __future__ import annotations

from app.plugins.wordle.plugin import WordlePlugin


def make_plugin(settings: dict | None = None) -> WordlePlugin:
    return WordlePlugin({"id": "wordle", "settings": settings or {}})


async def test_get_summary_returns_default_stats():
    plugin = make_plugin()

    assert await plugin.get_summary() == {
        "title": "Wordle",
        "stats": {"played": 0, "won": 0, "currentStreak": 0, "maxStreak": 0},
    }


async def test_get_summary_reflects_persisted_stats():
    plugin = make_plugin({"stats": {"played": 5, "won": 3, "currentStreak": 2, "maxStreak": 3}})

    summary = await plugin.get_summary()

    assert summary["stats"] == {"played": 5, "won": 3, "currentStreak": 2, "maxStreak": 3}


async def test_get_detail_matches_get_summary():
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()
