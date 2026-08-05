from __future__ import annotations

from typing import Any

from app.integrations import steam_client
from app.plugins.steam import news

GAMES = [
    {"appid": 220, "name": "Half-Life 2"},
    {"appid": 400, "name": "Portal"},
    {"appid": 620, "name": "Portal 2"},
]


def _news_item(appid: int, gid: str, date: int) -> dict[str, Any]:
    return {
        "gid": gid,
        "title": f"News {gid}",
        "url": f"https://store.steampowered.com/news/app/{appid}/view/{gid}",
        "author": "Valve",
        "contents": "",
        "feedlabel": "Updates",
        "date": date,
        "is_external_url": True,
    }


async def test_fetch_news_merges_and_sorts_by_date_descending(monkeypatch):
    async def fake_fetch(appid: int, count: int, maxlength: int) -> list[dict[str, Any]]:
        by_appid = {
            220: [_news_item(220, "hl2-old", 1000)],
            400: [_news_item(400, "portal-new", 3000)],
            620: [_news_item(620, "portal2-mid", 2000)],
        }
        return by_appid[appid]

    monkeypatch.setattr(steam_client, "fetch_news_for_app", fake_fetch)

    items, errors = await news.fetch_news(GAMES, count_per_game=5, limit=10)

    assert errors == []
    assert [i["gid"] for i in items] == ["portal-new", "portal2-mid", "hl2-old"]
    assert items[0]["appid"] == 400
    assert items[0]["game_name"] == "Portal"


async def test_fetch_news_truncates_to_limit_after_merging(monkeypatch):
    async def fake_fetch(appid: int, count: int, maxlength: int) -> list[dict[str, Any]]:
        return [_news_item(appid, f"{appid}-{i}", 1000 * i) for i in range(count)]

    monkeypatch.setattr(steam_client, "fetch_news_for_app", fake_fetch)

    items, errors = await news.fetch_news(GAMES, count_per_game=5, limit=3)

    assert errors == []
    assert len(items) == 3


async def test_fetch_news_isolates_errors_per_game(monkeypatch):
    async def fake_fetch(appid: int, count: int, maxlength: int) -> list[dict[str, Any]]:
        if appid == 400:
            raise steam_client.SteamError("boom")
        return [_news_item(appid, f"{appid}-1", 1000)]

    monkeypatch.setattr(steam_client, "fetch_news_for_app", fake_fetch)

    items, errors = await news.fetch_news(GAMES, count_per_game=5, limit=10)

    assert {i["appid"] for i in items} == {220, 620}
    assert errors == [{"appid": 400, "game_name": "Portal", "error": "boom"}]


async def test_fetch_news_returns_empty_for_no_games():
    items, errors = await news.fetch_news([], count_per_game=5, limit=10)

    assert items == []
    assert errors == []


async def test_fetch_news_is_cached_per_appid(monkeypatch):
    call_count = 0

    async def fake_fetch(appid: int, count: int, maxlength: int) -> list[dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        return [_news_item(appid, "gid", 1000)]

    monkeypatch.setattr(steam_client, "fetch_news_for_app", fake_fetch)

    await news.fetch_news(GAMES[:1], count_per_game=5, limit=10)
    await news.fetch_news(GAMES[:1], count_per_game=5, limit=10)

    assert call_count == 1


async def test_fetch_news_error_is_not_cached(monkeypatch):
    call_count = 0

    async def fake_fetch(appid: int, count: int, maxlength: int) -> list[dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        raise steam_client.SteamError("boom")

    monkeypatch.setattr(steam_client, "fetch_news_for_app", fake_fetch)

    _, first_errors = await news.fetch_news(GAMES[:1], count_per_game=5, limit=10)
    _, second_errors = await news.fetch_news(GAMES[:1], count_per_game=5, limit=10)

    assert len(first_errors) == 1
    assert len(second_errors) == 1
    assert call_count == 2
