from __future__ import annotations

from app.plugins.wordle.plugin import WordlePlugin


def make_plugin() -> WordlePlugin:
    return WordlePlugin({"id": "wordle", "settings": {}})


async def test_get_summary_returns_static_title():
    plugin = make_plugin()

    assert await plugin.get_summary() == {"title": "Wordle"}


async def test_get_detail_matches_get_summary():
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()
