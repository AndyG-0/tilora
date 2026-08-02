from __future__ import annotations

import httpx
import respx

from app.plugins.movies.plugin import TMDB_BASE_URL, MoviesPlugin

POPULAR_RESPONSE = {
    "results": [
        {
            "id": 1,
            "title": "Movie One",
            "release_date": "2026-01-01",
            "vote_average": 8.1,
            "poster_path": "/one.jpg",
            "overview": "First movie.",
        },
        {
            "id": 2,
            "title": "Movie Two",
            "release_date": "2026-02-02",
            "vote_average": 7.4,
            "poster_path": None,
            "overview": "Second movie.",
        },
    ]
}

TV_POPULAR_RESPONSE = {
    "results": [
        {
            "id": 11,
            "name": "Show One",
            "first_air_date": "2026-03-03",
            "vote_average": 9.0,
            "poster_path": "/show-one.jpg",
            "overview": "First show.",
        },
        {
            "id": 12,
            "name": "Show Two",
            "first_air_date": "2026-04-04",
            "vote_average": 6.8,
            "poster_path": None,
            "overview": "Second show.",
        },
    ]
}


TRENDING_TV_RESPONSE = {
    "results": [
        {
            "id": 21,
            "name": "Trending Show",
            "first_air_date": "2026-05-05",
            "vote_average": 8.5,
            "poster_path": "/trending.jpg",
            "overview": "A trending show.",
        }
    ]
}


def make_plugin(**settings) -> MoviesPlugin:
    return MoviesPlugin({"id": "movies", "settings": settings})


def _mock_popular() -> None:
    respx.get(f"{TMDB_BASE_URL}/movie/popular").mock(return_value=httpx.Response(200, json=POPULAR_RESPONSE))
    respx.get(f"{TMDB_BASE_URL}/tv/popular").mock(return_value=httpx.Response(200, json=TV_POPULAR_RESPONSE))
    respx.get(f"{TMDB_BASE_URL}/trending/tv/week").mock(return_value=httpx.Response(200, json=TRENDING_TV_RESPONSE))


@respx.mock
async def test_get_summary_maps_popular_movies_and_tv_shows():
    _mock_popular()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["movies"] == [
        {
            "id": 1,
            "title": "Movie One",
            "release_date": "2026-01-01",
            "rating": 8.1,
            "poster_url": "https://image.tmdb.org/t/p/w342/one.jpg",
        },
        {
            "id": 2,
            "title": "Movie Two",
            "release_date": "2026-02-02",
            "rating": 7.4,
            "poster_url": None,
        },
    ]
    assert summary["tv_shows"] == [
        {
            "id": 11,
            "title": "Show One",
            "release_date": "2026-03-03",
            "rating": 9.0,
            "poster_url": "https://image.tmdb.org/t/p/w342/show-one.jpg",
        },
        {
            "id": 12,
            "title": "Show Two",
            "release_date": "2026-04-04",
            "rating": 6.8,
            "poster_url": None,
        },
    ]
    assert summary["trending_tv_shows"] == [
        {
            "id": 21,
            "title": "Trending Show",
            "release_date": "2026-05-05",
            "rating": 8.5,
            "poster_url": "https://image.tmdb.org/t/p/w342/trending.jpg",
        },
    ]


@respx.mock
async def test_get_detail_includes_overview_and_watch_providers():
    _mock_popular()
    respx.get(f"{TMDB_BASE_URL}/movie/1/watch/providers").mock(
        return_value=httpx.Response(
            200,
            json={"results": {"US": {"flatrate": [{"provider_name": "Streamflix"}]}}},
        )
    )
    respx.get(f"{TMDB_BASE_URL}/movie/2/watch/providers").mock(return_value=httpx.Response(200, json={"results": {}}))
    respx.get(f"{TMDB_BASE_URL}/tv/11/watch/providers").mock(
        return_value=httpx.Response(
            200,
            json={"results": {"US": {"flatrate": [{"provider_name": "Showflix"}]}}},
        )
    )
    respx.get(f"{TMDB_BASE_URL}/tv/12/watch/providers").mock(return_value=httpx.Response(200, json={"results": {}}))
    respx.get(f"{TMDB_BASE_URL}/tv/21/watch/providers").mock(
        return_value=httpx.Response(
            200,
            json={"results": {"US": {"flatrate": [{"provider_name": "Trendflix"}]}}},
        )
    )
    plugin = make_plugin(region="US")

    detail = await plugin.get_detail()

    assert detail["region"] == "US"
    assert detail["movies"][0]["overview"] == "First movie."
    assert detail["movies"][0]["where_to_watch"] == ["Streamflix"]
    assert detail["movies"][1]["where_to_watch"] == []
    assert detail["tv_shows"][0]["overview"] == "First show."
    assert detail["tv_shows"][0]["where_to_watch"] == ["Showflix"]
    assert detail["tv_shows"][1]["where_to_watch"] == []
    assert detail["trending_tv_shows"][0]["overview"] == "A trending show."
    assert detail["trending_tv_shows"][0]["where_to_watch"] == ["Trendflix"]


@respx.mock
async def test_get_ai_tools_exposes_popular_movies_and_tv_show_tools():
    _mock_popular()
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert len(tools) == 2
    assert tools[0].name == "get_popular_movies"
    movies_result = await tools[0].handler()
    assert movies_result["movies"][0]["title"] == "Movie One"

    assert tools[1].name == "get_popular_tv_shows"
    tv_result = await tools[1].handler()
    assert tv_result["tv_shows"][0]["title"] == "Show One"


@respx.mock
async def test_get_summary_uses_trending_endpoints_in_trending_mode():
    respx.get(f"{TMDB_BASE_URL}/trending/movie/week").mock(return_value=httpx.Response(200, json=POPULAR_RESPONSE))
    respx.get(f"{TMDB_BASE_URL}/trending/tv/week").mock(return_value=httpx.Response(200, json=TV_POPULAR_RESPONSE))
    plugin = make_plugin(mode="trending")

    summary = await plugin.get_summary()

    assert summary["movies"][0]["title"] == "Movie One"
    assert summary["tv_shows"][0]["title"] == "Show One"


@respx.mock
async def test_get_ai_tools_description_reflects_trending_mode():
    _mock_popular()
    plugin = make_plugin(mode="trending")

    tools = plugin.get_ai_tools()

    assert "trending" in tools[0].description
    assert "trending" in tools[1].description
