"""Movies plugin: TMDB popular or trending movies/TV, drilling down into
JustWatch-sourced streaming availability (TMDB's `/watch/providers` endpoint
aggregates JustWatch data — no separate JustWatch API key needed).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import settings
from app.plugins.base import Plugin, ToolDef

TMDB_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w342"

# How many of the popular-movies/popular-tv results to enrich with
# watch-provider data in get_detail — each one is an extra TMDB request, so
# keep it bounded.
_DETAIL_ITEM_COUNT = 10
_SUMMARY_ITEM_COUNT = 5


class MoviesPlugin(Plugin):
    id = "movies"
    name = "Movies & Shows"
    refresh_interval_seconds = 3600

    @property
    def region(self) -> str:
        return self.config["settings"].get("region", "US")

    @property
    def mode(self) -> str:
        # "popular" (default) or "trending" — which TMDB list to show.
        return self.config["settings"].get("mode", "popular")

    @property
    def _params(self) -> dict[str, str]:
        return {"api_key": settings.tmdb_api_key or "", "language": "en-US"}

    def _list_path(self, media_type: str) -> str:
        if self.mode == "trending":
            return f"trending/{media_type}/week"
        return f"{media_type}/popular"

    async def _fetch_path(self, client: httpx.AsyncClient, path: str) -> list[dict[str, Any]]:
        response = await client.get(f"{TMDB_BASE_URL}/{path}", params=self._params)
        response.raise_for_status()
        return response.json()["results"]

    async def _fetch_list(self, client: httpx.AsyncClient, media_type: str) -> list[dict[str, Any]]:
        return await self._fetch_path(client, self._list_path(media_type))

    async def _fetch_trending_tv(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        # Always trending/tv/week regardless of `mode` — a dedicated
        # "what's trending" section alongside the popular/trending toggle
        # that already governs the Movies/Shows lists above.
        return await self._fetch_path(client, "trending/tv/week")

    async def _fetch_providers(self, client: httpx.AsyncClient, media_type: str, item_id: int) -> list[str]:
        response = await client.get(
            f"{TMDB_BASE_URL}/{media_type}/{item_id}/watch/providers",
            params={"api_key": settings.tmdb_api_key or ""},
        )
        response.raise_for_status()
        region_data = response.json().get("results", {}).get(self.region, {})
        return sorted({p["provider_name"] for p in region_data.get("flatrate", [])})

    def _media_summary(self, item: dict[str, Any], media_type: str) -> dict[str, Any]:
        # TV objects use `name`/`first_air_date` instead of movies'
        # `title`/`release_date` — normalize both to the same output keys so
        # callers (frontend, AI tools) don't need to special-case TV.
        is_movie = media_type == "movie"
        return {
            "id": item["id"],
            "title": item["title"] if is_movie else item["name"],
            "release_date": item.get("release_date" if is_movie else "first_air_date") or None,
            "rating": item.get("vote_average"),
            "poster_url": (f"{POSTER_BASE_URL}{item['poster_path']}" if item.get("poster_path") else None),
        }

    async def get_summary(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            movies, tv_shows, trending_tv = await asyncio.gather(
                self._fetch_list(client, "movie"),
                self._fetch_list(client, "tv"),
                self._fetch_trending_tv(client),
            )
        return {
            "movies": [self._media_summary(m, "movie") for m in movies[:_SUMMARY_ITEM_COUNT]],
            "tv_shows": [self._media_summary(t, "tv") for t in tv_shows[:_SUMMARY_ITEM_COUNT]],
            "trending_tv_shows": [self._media_summary(t, "tv") for t in trending_tv[:_SUMMARY_ITEM_COUNT]],
        }

    async def get_detail(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            movies, tv_shows, trending_tv = await asyncio.gather(
                self._fetch_list(client, "movie"),
                self._fetch_list(client, "tv"),
                self._fetch_trending_tv(client),
            )
            top_movies = movies[:_DETAIL_ITEM_COUNT]
            top_tv = tv_shows[:_DETAIL_ITEM_COUNT]
            top_trending_tv = trending_tv[:_DETAIL_ITEM_COUNT]
            movie_providers, tv_providers, trending_tv_providers = await asyncio.gather(
                asyncio.gather(*(self._fetch_providers(client, "movie", m["id"]) for m in top_movies)),
                asyncio.gather(*(self._fetch_providers(client, "tv", t["id"]) for t in top_tv)),
                asyncio.gather(*(self._fetch_providers(client, "tv", t["id"]) for t in top_trending_tv)),
            )

        movies_out = [
            {**self._media_summary(m, "movie"), "overview": m.get("overview", ""), "where_to_watch": p}
            for m, p in zip(top_movies, movie_providers, strict=True)
        ]
        tv_out = [
            {**self._media_summary(t, "tv"), "overview": t.get("overview", ""), "where_to_watch": p}
            for t, p in zip(top_tv, tv_providers, strict=True)
        ]
        trending_tv_out = [
            {**self._media_summary(t, "tv"), "overview": t.get("overview", ""), "where_to_watch": p}
            for t, p in zip(top_trending_tv, trending_tv_providers, strict=True)
        ]
        return {
            "movies": movies_out,
            "tv_shows": tv_out,
            "trending_tv_shows": trending_tv_out,
            "region": self.region,
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_popular_movies() -> dict[str, Any]:
            summary = await self.get_summary()
            return {"movies": summary["movies"]}

        async def get_popular_tv_shows() -> dict[str, Any]:
            summary = await self.get_summary()
            return {"tv_shows": summary["tv_shows"]}

        list_label = "trending this week" if self.mode == "trending" else "popular"
        return [
            ToolDef(
                name="get_popular_movies",
                description=f"Get the current list of {list_label} movies from TMDB.",
                parameters={"type": "object", "properties": {}},
                handler=get_popular_movies,
            ),
            ToolDef(
                name="get_popular_tv_shows",
                description=f"Get the current list of {list_label} TV shows from TMDB.",
                parameters={"type": "object", "properties": {}},
                handler=get_popular_tv_shows,
            ),
        ]
