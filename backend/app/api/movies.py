"""Streaming-provider catalog for the movies widget's settings editor.

Backed by TMDB's /watch/providers/movie and /watch/providers/tv, merged and
deduped by provider_id so the settings UI can present one flat list
regardless of whether a service is flagged for movies, TV, or both.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.config import settings

TMDB_BASE_URL = "https://api.themoviedb.org/3"
PROVIDER_LOGO_BASE_URL = "https://image.tmdb.org/t/p/w45"

router = APIRouter(prefix="/api/movies", tags=["movies"])


async def _fetch_providers(client: httpx.AsyncClient, media_type: str, region: str) -> list[dict[str, Any]]:
    response = await client.get(
        f"{TMDB_BASE_URL}/watch/providers/{media_type}",
        params={"api_key": settings.tmdb_api_key or "", "watch_region": region},
    )
    response.raise_for_status()
    return response.json().get("results", [])


@router.get("/providers")
async def list_providers(region: str = Query("US")) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        movie_results, tv_results = await asyncio.gather(
            _fetch_providers(client, "movie", region),
            _fetch_providers(client, "tv", region),
        )

    merged: dict[int, dict[str, Any]] = {}
    for provider in [*movie_results, *tv_results]:
        provider_id = provider["provider_id"]
        priority = provider.get("display_priority", 999)
        if provider_id not in merged or priority < merged[provider_id]["_priority"]:
            merged[provider_id] = {
                "id": provider_id,
                "name": provider["provider_name"],
                "logo_url": f"{PROVIDER_LOGO_BASE_URL}{provider['logo_path']}" if provider.get("logo_path") else None,
                "_priority": priority,
            }

    ordered = sorted(merged.values(), key=lambda p: (p["_priority"], p["name"].lower()))
    return [{"id": p["id"], "name": p["name"], "logo_url": p["logo_url"]} for p in ordered]
