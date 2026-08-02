"""City lookup for the weather widget's location setting.

Backed by Open-Meteo's geocoding API (no API key required), matching the
weather plugin itself.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Query

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/search")
async def search_cities(q: str = Query(min_length=1)) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GEOCODING_URL,
            params={"name": q, "count": 10, "language": "en", "format": "json"},
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "name": result["name"],
            "admin1": result.get("admin1"),
            "country": result.get("country"),
            "latitude": result["latitude"],
            "longitude": result["longitude"],
        }
        for result in data.get("results", [])
    ]
