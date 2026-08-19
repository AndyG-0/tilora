from __future__ import annotations

import httpx
import pytest
import respx

from app import config
from app.plugins.movies.plugin import TMDB_BASE_URL, MoviesPlugin


@pytest.fixture(autouse=True)
def _set_tmdb_api_key(monkeypatch):
    monkeypatch.setattr(config.settings, "tmdb_api_key", "test-tmdb-key")


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

TRENDING_MOVIE_RESPONSE = {
    "results": [
        {
            "id": 31,
            "title": "Trending Movie",
            "release_date": "2026-06-06",
            "vote_average": 7.9,
            "poster_path": "/trending-movie.jpg",
            "overview": "A trending movie.",
        }
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

ON_STREAMING_MOVIE_RESPONSE = {
    "results": [
        {
            "id": 41,
            "title": "Streaming Movie",
            "release_date": "2026-07-07",
            "vote_average": 6.5,
            "poster_path": "/streaming-movie.jpg",
            "overview": "A streaming movie.",
        }
    ]
}

ON_STREAMING_TV_RESPONSE = {
    "results": [
        {
            "id": 42,
            "name": "Streaming Show",
            "first_air_date": "2026-08-08",
            "vote_average": 7.1,
            "poster_path": "/streaming-show.jpg",
            "overview": "A streaming show.",
        }
    ]
}


def make_plugin(**settings) -> MoviesPlugin:
    return MoviesPlugin({"id": "movies", "settings": settings})


def _mock_all_lists() -> None:
    respx.get(f"{TMDB_BASE_URL}/movie/popular").mock(return_value=httpx.Response(200, json=POPULAR_RESPONSE))
    respx.get(f"{TMDB_BASE_URL}/tv/popular").mock(return_value=httpx.Response(200, json=TV_POPULAR_RESPONSE))
    respx.get(f"{TMDB_BASE_URL}/trending/movie/week").mock(
        return_value=httpx.Response(200, json=TRENDING_MOVIE_RESPONSE)
    )
    respx.get(f"{TMDB_BASE_URL}/trending/tv/week").mock(return_value=httpx.Response(200, json=TRENDING_TV_RESPONSE))
    respx.get(f"{TMDB_BASE_URL}/discover/movie").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_MOVIE_RESPONSE)
    )
    respx.get(f"{TMDB_BASE_URL}/discover/tv").mock(return_value=httpx.Response(200, json=ON_STREAMING_TV_RESPONSE))


@respx.mock
async def test_get_summary_returns_all_six_keys_by_default():
    _mock_all_lists()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["popular_movies"][0]["title"] == "Movie One"
    assert summary["popular_tv_shows"][0]["title"] == "Show One"
    assert summary["trending_movies"][0]["title"] == "Trending Movie"
    assert summary["trending_tv_shows"][0]["title"] == "Trending Show"
    assert summary["on_streaming_movies"][0]["title"] == "Streaming Movie"
    assert summary["on_streaming_tv_shows"][0]["title"] == "Streaming Show"
    assert summary["popular_movies"] == [
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


@respx.mock
async def test_get_summary_respects_categories_setting():
    popular_route = respx.get(f"{TMDB_BASE_URL}/movie/popular").mock(
        return_value=httpx.Response(200, json=POPULAR_RESPONSE)
    )
    tv_route = respx.get(f"{TMDB_BASE_URL}/tv/popular").mock(return_value=httpx.Response(200, json=TV_POPULAR_RESPONSE))
    trending_movie_route = respx.get(f"{TMDB_BASE_URL}/trending/movie/week").mock(
        return_value=httpx.Response(200, json=TRENDING_MOVIE_RESPONSE)
    )
    trending_tv_route = respx.get(f"{TMDB_BASE_URL}/trending/tv/week").mock(
        return_value=httpx.Response(200, json=TRENDING_TV_RESPONSE)
    )
    discover_movie_route = respx.get(f"{TMDB_BASE_URL}/discover/movie").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_MOVIE_RESPONSE)
    )
    discover_tv_route = respx.get(f"{TMDB_BASE_URL}/discover/tv").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_TV_RESPONSE)
    )
    plugin = make_plugin(categories=["popular_movies"])

    summary = await plugin.get_summary()

    assert [k for k in summary.keys() if k != "configured"] == ["popular_movies"]
    assert popular_route.called
    assert not tv_route.called
    assert not trending_movie_route.called
    assert not trending_tv_route.called
    assert not discover_movie_route.called
    assert not discover_tv_route.called


@respx.mock
async def test_get_summary_ignores_unknown_category_values():
    respx.get(f"{TMDB_BASE_URL}/movie/popular").mock(return_value=httpx.Response(200, json=POPULAR_RESPONSE))
    plugin = make_plugin(categories=["popular_movies", "bogus"])

    summary = await plugin.get_summary()

    assert [k for k in summary.keys() if k != "configured"] == ["popular_movies"]


@respx.mock
async def test_on_streaming_uses_generic_flatrate_discover_params_when_no_providers():
    discover_movie_route = respx.get(f"{TMDB_BASE_URL}/discover/movie").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_MOVIE_RESPONSE)
    )
    discover_tv_route = respx.get(f"{TMDB_BASE_URL}/discover/tv").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_TV_RESPONSE)
    )
    plugin = make_plugin(categories=["on_streaming"], region="GB")

    await plugin.get_summary()

    movie_params = discover_movie_route.calls.last.request.url.params
    assert movie_params["watch_region"] == "GB"
    assert movie_params["with_watch_monetization_types"] == "flatrate"
    assert movie_params["sort_by"] == "popularity.desc"
    assert "with_watch_providers" not in movie_params

    tv_params = discover_tv_route.calls.last.request.url.params
    assert tv_params["watch_region"] == "GB"
    assert "with_watch_providers" not in tv_params


@respx.mock
async def test_on_streaming_narrows_to_selected_providers():
    discover_movie_route = respx.get(f"{TMDB_BASE_URL}/discover/movie").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_MOVIE_RESPONSE)
    )
    discover_tv_route = respx.get(f"{TMDB_BASE_URL}/discover/tv").mock(
        return_value=httpx.Response(200, json=ON_STREAMING_TV_RESPONSE)
    )
    plugin = make_plugin(categories=["on_streaming"], providers=[8, 337])

    await plugin.get_summary()

    assert discover_movie_route.calls.last.request.url.params["with_watch_providers"] == "8,337"
    assert discover_tv_route.calls.last.request.url.params["with_watch_providers"] == "8,337"


@respx.mock
async def test_get_detail_includes_overview_watch_providers_region_categories_and_providers():
    _mock_all_lists()
    respx.get(f"{TMDB_BASE_URL}/movie/1/watch/providers").mock(
        return_value=httpx.Response(
            200,
            json={"results": {"US": {"flatrate": [{"provider_name": "Netflix", "logo_path": "/netflix.jpg"}]}}},
        )
    )
    respx.get(f"{TMDB_BASE_URL}/movie/2/watch/providers").mock(return_value=httpx.Response(200, json={"results": {}}))
    respx.get(f"{TMDB_BASE_URL}/tv/11/watch/providers").mock(
        return_value=httpx.Response(
            200,
            json={"results": {"US": {"flatrate": [{"provider_name": "Showflix", "logo_path": "/showflix.jpg"}]}}},
        )
    )
    respx.get(f"{TMDB_BASE_URL}/tv/12/watch/providers").mock(return_value=httpx.Response(200, json={"results": {}}))
    respx.get(f"{TMDB_BASE_URL}/movie/31/watch/providers").mock(
        return_value=httpx.Response(200, json={"results": {"US": {"flatrate": [{"provider_name": "Trendflix"}]}}})
    )
    respx.get(f"{TMDB_BASE_URL}/tv/21/watch/providers").mock(
        return_value=httpx.Response(200, json={"results": {"US": {"flatrate": [{"provider_name": "Trendflix"}]}}})
    )
    respx.get(f"{TMDB_BASE_URL}/movie/41/watch/providers").mock(
        return_value=httpx.Response(200, json={"results": {"US": {"flatrate": [{"provider_name": "Netflix"}]}}})
    )
    respx.get(f"{TMDB_BASE_URL}/tv/42/watch/providers").mock(
        return_value=httpx.Response(200, json={"results": {"US": {"flatrate": [{"provider_name": "Showflix"}]}}})
    )
    plugin = make_plugin(region="US", providers=[8])

    detail = await plugin.get_detail()

    assert detail["region"] == "US"
    assert detail["categories"] == [
        "popular_movies",
        "popular_tv",
        "trending_movies",
        "trending_tv",
        "on_streaming",
    ]
    assert detail["providers"] == [8]
    assert detail["popular_movies"][0]["overview"] == "First movie."
    assert detail["popular_movies"][0]["where_to_watch"] == [
        {"name": "Netflix", "logo_url": "https://image.tmdb.org/t/p/w45/netflix.jpg", "url": "https://www.netflix.com"}
    ]
    assert detail["popular_movies"][1]["where_to_watch"] == []
    assert detail["popular_tv_shows"][0]["overview"] == "First show."
    assert detail["popular_tv_shows"][0]["where_to_watch"] == [
        {"name": "Showflix", "logo_url": "https://image.tmdb.org/t/p/w45/showflix.jpg", "url": None}
    ]
    assert detail["trending_movies"][0]["where_to_watch"] == [{"name": "Trendflix", "logo_url": None, "url": None}]
    assert detail["trending_tv_shows"][0]["where_to_watch"] == [{"name": "Trendflix", "logo_url": None, "url": None}]
    assert detail["on_streaming_movies"][0]["where_to_watch"] == [
        {"name": "Netflix", "logo_url": None, "url": "https://www.netflix.com"}
    ]
    assert detail["on_streaming_tv_shows"][0]["where_to_watch"] == [{"name": "Showflix", "logo_url": None, "url": None}]


@respx.mock
async def test_get_ai_tools_exposes_six_tools_with_expected_names():
    _mock_all_lists()
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert [tool.name for tool in tools] == [
        "get_popular_movies",
        "get_trending_movies",
        "get_popular_tv_shows",
        "get_trending_tv_shows",
        "get_on_streaming_movies",
        "get_on_streaming_tv_shows",
    ]

    popular_movies = await tools[0].handler()
    assert popular_movies["movies"][0]["title"] == "Movie One"

    trending_movies = await tools[1].handler()
    assert trending_movies["movies"][0]["title"] == "Trending Movie"

    popular_tv = await tools[2].handler()
    assert popular_tv["tv_shows"][0]["title"] == "Show One"

    trending_tv = await tools[3].handler()
    assert trending_tv["tv_shows"][0]["title"] == "Trending Show"

    on_streaming_movies = await tools[4].handler()
    assert on_streaming_movies["movies"][0]["title"] == "Streaming Movie"

    on_streaming_tv = await tools[5].handler()
    assert on_streaming_tv["tv_shows"][0]["title"] == "Streaming Show"


@respx.mock
async def test_get_ai_tools_always_present_regardless_of_categories_setting():
    _mock_all_lists()
    plugin = make_plugin(categories=["popular_movies"])

    tools = plugin.get_ai_tools()

    assert len(tools) == 6
    trending_tv_result = await tools[3].handler()
    assert trending_tv_result["tv_shows"][0]["title"] == "Trending Show"


@respx.mock
async def test_get_ai_tools_descriptions_distinguish_popular_from_trending():
    plugin = make_plugin()

    tools = {tool.name: tool for tool in plugin.get_ai_tools()}

    assert tools["get_popular_movies"].description.startswith("Get the all-time popular")
    assert tools["get_trending_movies"].description.startswith("Get this week's trending")
    assert tools["get_popular_tv_shows"].description.startswith("Get the all-time popular")
    assert tools["get_trending_tv_shows"].description.startswith("Get this week's trending")


def test_get_ai_tools_on_streaming_description_is_generic_without_providers():
    plugin = make_plugin()

    tools = {tool.name: tool for tool in plugin.get_ai_tools()}

    assert "generic" in tools["get_on_streaming_movies"].description.lower()
    assert "generic" in tools["get_on_streaming_tv_shows"].description.lower()


def test_get_ai_tools_on_streaming_description_mentions_provider_count_when_set():
    plugin = make_plugin(providers=[8, 337])

    tools = {tool.name: tool for tool in plugin.get_ai_tools()}

    assert "2 streaming service" in tools["get_on_streaming_movies"].description
    assert "2 streaming service" in tools["get_on_streaming_tv_shows"].description


@respx.mock
async def test_unconfigured_movies_plugin_returns_empty_and_not_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "tmdb_api_key", None)
    plugin = make_plugin()

    summary = await plugin.get_summary()
    assert summary["configured"] is False
    assert summary["popular_movies"] == []
    assert summary["popular_tv_shows"] == []

    detail = await plugin.get_detail()
    assert detail["configured"] is False
    assert detail["popular_movies"] == []
    assert detail["popular_tv_shows"] == []


@respx.mock
async def test_movies_plugin_handles_tmdb_http_error_gracefully():
    respx.get(f"{TMDB_BASE_URL}/movie/popular").mock(return_value=httpx.Response(500))
    respx.get(f"{TMDB_BASE_URL}/tv/popular").mock(return_value=httpx.Response(401))
    respx.get(f"{TMDB_BASE_URL}/trending/movie/week").mock(return_value=httpx.Response(500))
    respx.get(f"{TMDB_BASE_URL}/trending/tv/week").mock(return_value=httpx.Response(500))
    respx.get(f"{TMDB_BASE_URL}/discover/movie").mock(return_value=httpx.Response(500))
    respx.get(f"{TMDB_BASE_URL}/discover/tv").mock(return_value=httpx.Response(500))

    plugin = make_plugin()
    summary = await plugin.get_summary()
    assert summary["configured"] is True
    assert summary["popular_movies"] == []
    assert summary["popular_tv_shows"] == []

    detail = await plugin.get_detail()
    assert detail["configured"] is True
    assert detail["popular_movies"] == []
