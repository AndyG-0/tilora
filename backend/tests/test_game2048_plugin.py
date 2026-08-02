from __future__ import annotations

from app.plugins.game2048.plugin import Game2048Plugin


def make_plugin() -> Game2048Plugin:
    return Game2048Plugin({"id": "game2048", "settings": {}})


async def test_get_summary_returns_static_title():
    plugin = make_plugin()

    assert await plugin.get_summary() == {"title": "2048"}


async def test_get_detail_matches_get_summary():
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()
