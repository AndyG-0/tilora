from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.api import movies
from app.api.movies import TMDB_BASE_URL


@pytest.fixture(autouse=True)
def _set_tmdb_api_key(monkeypatch, tmp_db):
    # `effective_settings()` (used by the /movies endpoint) now reads through
    # to the db-persisted app_settings table, so every test needs an isolated
    # db (`tmp_db`) rather than hitting the real ambient one.
    monkeypatch.setattr(config.settings, "tmdb_api_key", "test-tmdb-key")


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(movies.router)
    return TestClient(app)


def _provider(provider_id: int, name: str, logo_path: str | None, priority: int) -> dict:
    return {
        "provider_id": provider_id,
        "provider_name": name,
        "logo_path": logo_path,
        "display_priority": priority,
    }


@respx.mock
def test_list_providers_merges_and_dedupes_movie_and_tv_results():
    respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _provider(8, "Netflix", "/netflix.jpg", 0),
                    _provider(9, "Prime Video", "/prime.jpg", 2),
                ]
            },
        )
    )
    respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _provider(8, "Netflix", "/netflix.jpg", 0),
                    _provider(337, "Disney Plus", "/disney.jpg", 1),
                ]
            },
        )
    )
    client = make_client()

    response = client.get("/api/movies/providers")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 8, "name": "Netflix", "logo_url": "https://image.tmdb.org/t/p/w45/netflix.jpg"},
        {"id": 337, "name": "Disney Plus", "logo_url": "https://image.tmdb.org/t/p/w45/disney.jpg"},
        {"id": 9, "name": "Prime Video", "logo_url": "https://image.tmdb.org/t/p/w45/prime.jpg"},
    ]


@respx.mock
def test_list_providers_builds_logo_url_from_logo_path():
    respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(
        return_value=httpx.Response(
            200,
            json={"results": [_provider(1, "No Logo", None, 0)]},
        )
    )
    respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(return_value=httpx.Response(200, json={"results": []}))
    client = make_client()

    response = client.get("/api/movies/providers")

    assert response.json() == [{"id": 1, "name": "No Logo", "logo_url": None}]


@respx.mock
def test_list_providers_defaults_region_to_us():
    movie_route = respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    tv_route = respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = make_client()

    client.get("/api/movies/providers")

    assert movie_route.calls.last.request.url.params["watch_region"] == "US"
    assert tv_route.calls.last.request.url.params["watch_region"] == "US"


@respx.mock
def test_list_providers_sorts_by_display_priority():
    respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _provider(1, "Z Service", None, 5),
                    _provider(2, "A Service", None, 1),
                ]
            },
        )
    )
    respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(return_value=httpx.Response(200, json={"results": []}))
    client = make_client()

    response = client.get("/api/movies/providers")

    assert [p["name"] for p in response.json()] == ["A Service", "Z Service"]


@respx.mock
def test_list_providers_handles_empty_results():
    respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(return_value=httpx.Response(200, json={"results": []}))
    client = make_client()

    response = client.get("/api/movies/providers")

    assert response.status_code == 200
    assert response.json() == []


@respx.mock
def test_list_providers_passes_custom_region():
    movie_route = respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(return_value=httpx.Response(200, json={"results": []}))
    client = make_client()

    client.get("/api/movies/providers", params={"region": "GB"})

    assert movie_route.calls.last.request.url.params["watch_region"] == "GB"


@respx.mock
def test_list_providers_returns_empty_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config.settings, "tmdb_api_key", None)
    client = make_client()
    response = client.get("/api/movies/providers")
    assert response.status_code == 200
    assert response.json() == []


@respx.mock
def test_list_providers_handles_tmdb_http_error():
    respx.get(f"{TMDB_BASE_URL}/watch/providers/movie").mock(return_value=httpx.Response(500))
    respx.get(f"{TMDB_BASE_URL}/watch/providers/tv").mock(return_value=httpx.Response(500))
    client = make_client()
    response = client.get("/api/movies/providers")
    assert response.status_code == 200
    assert response.json() == []
