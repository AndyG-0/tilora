"""Movies plugin: TMDB popular, trending, and on-streaming movies/TV, drilling
down into JustWatch-sourced streaming availability (TMDB's `/watch/providers`
endpoint aggregates JustWatch data — no separate JustWatch API key needed).

Which sections a widget shows is controlled by the `categories` setting (a
list of category keys, defaulting to all of them); which streaming services
narrow the "on streaming" section is controlled by the `providers` setting
(a list of TMDB provider IDs, see `app.api.movies`). Both are editable from
the widget's detail view. The AI assistant's tools are NOT gated by
`categories` — a voice query can always ask about any of the six lists below
regardless of what's currently visible on the dashboard.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import settings
from app.plugins.base import Plugin, ToolDef
from app.storage.cache import cached_call

TMDB_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w342"
PROVIDER_LOGO_BASE_URL = "https://image.tmdb.org/t/p/w45"

# TMDB's /watch/providers endpoint doesn't return a per-provider deep link —
# only a single aggregated attribution page for the whole title. Rather than
# send every provider chip to that same shared link, point each known
# provider at its own service homepage; providers not in this map render as
# non-clickable chips instead of guessing a URL.
_PROVIDER_HOME_URLS: dict[str, str] = {
    "Netflix": "https://www.netflix.com",
    "Hulu": "https://www.hulu.com",
    "Disney Plus": "https://www.disneyplus.com",
    "Max": "https://www.max.com",
    "HBO Max": "https://www.max.com",
    "Amazon Prime Video": "https://www.amazon.com/gp/video/storefront",
    "Apple TV Plus": "https://tv.apple.com",
    "Apple TV+": "https://tv.apple.com",
    "Paramount Plus": "https://www.paramountplus.com",
    "Peacock": "https://www.peacocktv.com",
    "Peacock Premium": "https://www.peacocktv.com",
    "YouTube": "https://www.youtube.com",
    "ESPN Plus": "https://plus.espn.com",
    "Starz": "https://www.starz.com",
    "Showtime": "https://www.showtime.com",
    "fuboTV": "https://www.fubo.tv",
    "Crunchyroll": "https://www.crunchyroll.com",
    "Tubi": "https://tubitv.com",
    "Pluto TV": "https://pluto.tv",
    "AMC+": "https://www.amcplus.com",
    "discovery+": "https://www.discoveryplus.com",
}

# How many of each list's results to enrich with watch-provider data in
# get_detail — each one is an extra TMDB request, so keep it bounded.
_DETAIL_ITEM_COUNT = 10
_SUMMARY_ITEM_COUNT = 5

# Per-item streaming-provider lookups are cached independently of the
# widget-level summary/detail cache (see _fetch_providers) — a title's
# flatrate availability changes on the order of days, not within the hour
# the outer widget cache already covers, and caching per-(region, media
# type, item id) means every widget/user asking about the same title shares
# one TMDB call instead of each re-fetching it.
_PROVIDER_CACHE_TTL_SECONDS = 24 * 60 * 60

# Settings-facing category keys, in canonical display/response order.
_ALL_CATEGORIES: tuple[str, ...] = (
    "popular_movies",
    "popular_tv",
    "trending_movies",
    "trending_tv",
    "on_streaming",
)

# response key -> the settings category that enables it. "on_streaming"
# fans out to two response keys since movie/TV ids aren't unique across
# each other and every other category is already movie/tv-split.
_CATEGORY_BY_RESPONSE_KEY: dict[str, str] = {
    "popular_movies": "popular_movies",
    "trending_movies": "trending_movies",
    "popular_tv_shows": "popular_tv",
    "trending_tv_shows": "trending_tv",
    "on_streaming_movies": "on_streaming",
    "on_streaming_tv_shows": "on_streaming",
}

_MEDIA_TYPE_BY_RESPONSE_KEY: dict[str, str] = {
    "popular_movies": "movie",
    "trending_movies": "movie",
    "on_streaming_movies": "movie",
    "popular_tv_shows": "tv",
    "trending_tv_shows": "tv",
    "on_streaming_tv_shows": "tv",
}


class MoviesPlugin(Plugin):
    id = "movies"
    name = "Movies & Shows"
    refresh_interval_seconds = 3600

    @property
    def region(self) -> str:
        return self.config["settings"].get("region", "US")

    @property
    def categories(self) -> list[str]:
        # Defaults to every category when unset. Filters out unrecognized
        # values defensively, since widget settings have no schema layer.
        raw = self.config["settings"].get("categories")
        if raw is None:
            return list(_ALL_CATEGORIES)
        enabled = set(raw)
        return [c for c in _ALL_CATEGORIES if c in enabled]

    @property
    def providers(self) -> list[int]:
        # TMDB provider IDs the user picked as their streaming services.
        # Empty (default) means on_streaming stays generic/unfiltered.
        return [int(p) for p in self.config["settings"].get("providers", [])]

    @property
    def _params(self) -> dict[str, str]:
        return {"api_key": settings.tmdb_api_key or "", "language": "en-US"}

    def _list_request(self, response_key: str) -> tuple[str, dict[str, str]]:
        if response_key == "popular_movies":
            return "movie/popular", {}
        if response_key == "popular_tv_shows":
            return "tv/popular", {}
        if response_key == "trending_movies":
            return "trending/movie/week", {}
        if response_key == "trending_tv_shows":
            return "trending/tv/week", {}
        # on_streaming_movies / on_streaming_tv_shows
        path = "discover/movie" if response_key == "on_streaming_movies" else "discover/tv"
        params = {
            "watch_region": self.region,
            "with_watch_monetization_types": "flatrate",
            "sort_by": "popularity.desc",
        }
        if self.providers:
            params["with_watch_providers"] = ",".join(str(p) for p in self.providers)
        return path, params

    def _enabled_response_keys(self) -> list[str]:
        enabled = set(self.categories)
        return [key for key, category in _CATEGORY_BY_RESPONSE_KEY.items() if category in enabled]

    async def _fetch_path(
        self, client: httpx.AsyncClient, path: str, extra_params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        response = await client.get(f"{TMDB_BASE_URL}/{path}", params={**self._params, **(extra_params or {})})
        response.raise_for_status()
        return response.json()["results"]

    async def _fetch_response_list(self, client: httpx.AsyncClient, response_key: str) -> list[dict[str, Any]]:
        path, extra_params = self._list_request(response_key)
        return await self._fetch_path(client, path, extra_params)

    async def _fetch_providers_uncached(
        self, client: httpx.AsyncClient, media_type: str, item_id: int
    ) -> list[dict[str, Any]]:
        response = await client.get(
            f"{TMDB_BASE_URL}/{media_type}/{item_id}/watch/providers",
            params={"api_key": settings.tmdb_api_key or ""},
        )
        response.raise_for_status()
        region_data = response.json().get("results", {}).get(self.region, {})
        return [
            {
                "name": p["provider_name"],
                "logo_url": f"{PROVIDER_LOGO_BASE_URL}{p['logo_path']}" if p.get("logo_path") else None,
                "url": _PROVIDER_HOME_URLS.get(p["provider_name"]),
            }
            for p in sorted(region_data.get("flatrate", []), key=lambda p: p["provider_name"])
        ]

    async def _fetch_providers(self, client: httpx.AsyncClient, media_type: str, item_id: int) -> list[dict[str, Any]]:
        key = f"movies:providers:{self.region}:{media_type}:{item_id}"
        return await cached_call(
            key, _PROVIDER_CACHE_TTL_SECONDS, lambda: self._fetch_providers_uncached(client, media_type, item_id)
        )

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
        keys = self._enabled_response_keys()
        async with httpx.AsyncClient(timeout=10) as client:
            lists = await asyncio.gather(*(self._fetch_response_list(client, key) for key in keys))
        return {
            key: [self._media_summary(item, _MEDIA_TYPE_BY_RESPONSE_KEY[key]) for item in items[:_SUMMARY_ITEM_COUNT]]
            for key, items in zip(keys, lists, strict=True)
        }

    async def get_detail(self) -> dict[str, Any]:
        keys = self._enabled_response_keys()
        async with httpx.AsyncClient(timeout=10) as client:
            lists = await asyncio.gather(*(self._fetch_response_list(client, key) for key in keys))
            top_items = {key: items[:_DETAIL_ITEM_COUNT] for key, items in zip(keys, lists, strict=True)}
            provider_lists = await asyncio.gather(
                *(
                    asyncio.gather(
                        *(self._fetch_providers(client, _MEDIA_TYPE_BY_RESPONSE_KEY[key], item["id"]) for item in items)
                    )
                    for key, items in top_items.items()
                )
            )

        result: dict[str, Any] = {"region": self.region, "categories": self.categories, "providers": self.providers}
        for key, item_providers in zip(top_items.keys(), provider_lists, strict=True):
            media_type = _MEDIA_TYPE_BY_RESPONSE_KEY[key]
            result[key] = [
                {**self._media_summary(item, media_type), "overview": item.get("overview", ""), "where_to_watch": p}
                for item, p in zip(top_items[key], item_providers, strict=True)
            ]
        return result

    def get_ai_tools(self) -> list[ToolDef]:
        async def fetch_one(response_key: str) -> list[dict[str, Any]]:
            async with httpx.AsyncClient(timeout=10) as client:
                items = await self._fetch_response_list(client, response_key)
            media_type = _MEDIA_TYPE_BY_RESPONSE_KEY[response_key]
            return [self._media_summary(item, media_type) for item in items[:_SUMMARY_ITEM_COUNT]]

        async def get_popular_movies() -> dict[str, Any]:
            return {"movies": await fetch_one("popular_movies")}

        async def get_trending_movies() -> dict[str, Any]:
            return {"movies": await fetch_one("trending_movies")}

        async def get_popular_tv_shows() -> dict[str, Any]:
            return {"tv_shows": await fetch_one("popular_tv_shows")}

        async def get_trending_tv_shows() -> dict[str, Any]:
            return {"tv_shows": await fetch_one("trending_tv_shows")}

        async def get_on_streaming_movies() -> dict[str, Any]:
            return {"movies": await fetch_one("on_streaming_movies")}

        async def get_on_streaming_tv_shows() -> dict[str, Any]:
            return {"tv_shows": await fetch_one("on_streaming_tv_shows")}

        streaming_scope = (
            f"scoped to the {len(self.providers)} streaming service(s) the user has selected"
            if self.providers
            else f"generic — any service offering a flatrate subscription in {self.region}, since no "
            "streaming services are selected"
        )
        return [
            ToolDef(
                name="get_popular_movies",
                description="Get the all-time popular movies list from TMDB (not this week's trending list).",
                parameters={"type": "object", "properties": {}},
                handler=get_popular_movies,
            ),
            ToolDef(
                name="get_trending_movies",
                description=(
                    "Get this week's trending movies from TMDB — the movies people are watching right now, "
                    "as opposed to the all-time popular list."
                ),
                parameters={"type": "object", "properties": {}},
                handler=get_trending_movies,
            ),
            ToolDef(
                name="get_popular_tv_shows",
                description="Get the all-time popular TV shows list from TMDB (not this week's trending list).",
                parameters={"type": "object", "properties": {}},
                handler=get_popular_tv_shows,
            ),
            ToolDef(
                name="get_trending_tv_shows",
                description=(
                    "Get this week's trending TV shows from TMDB — the shows people are watching right now, "
                    "as opposed to the all-time popular list."
                ),
                parameters={"type": "object", "properties": {}},
                handler=get_trending_tv_shows,
            ),
            ToolDef(
                name="get_on_streaming_movies",
                description=f"Get movies currently available to stream on a flatrate subscription, {streaming_scope}.",
                parameters={"type": "object", "properties": {}},
                handler=get_on_streaming_movies,
            ),
            ToolDef(
                name="get_on_streaming_tv_shows",
                description=(
                    f"Get TV shows currently available to stream on a flatrate subscription, {streaming_scope}."
                ),
                parameters={"type": "object", "properties": {}},
                handler=get_on_streaming_tv_shows,
            ),
        ]
