from __future__ import annotations

from app.plugins.game2048.plugin import Game2048Plugin


def make_plugin(settings: dict | None = None) -> Game2048Plugin:
    return Game2048Plugin({"id": "game2048", "settings": settings or {}})


async def test_get_summary_returns_default_best_score():
    plugin = make_plugin()

    assert await plugin.get_summary() == {"title": "2048", "best_score": 0}


async def test_get_summary_reflects_persisted_best_score():
    plugin = make_plugin({"best_score": 512})

    assert (await plugin.get_summary())["best_score"] == 512


async def test_get_detail_matches_get_summary():
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()
