"""Nominatim geocoding/reverse-geocoding client (nominatim.openstreetmap.org).

No API key required, but Nominatim's usage policy requires a descriptive
User-Agent identifying the application and caps usage at roughly one request
per second — callers should cache results rather than throttle client-side.
See https://operations.osmfoundation.org/policies/nominatim/
"""

from __future__ import annotations

from typing import Any

import httpx

SEARCH_URL = "https://nominatim.openstreetmap.org/search"
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

_HEADERS = {"User-Agent": "Tilora self-hosted dashboard (mapping integration)"}


class NominatimError(Exception):
    """Raised when Nominatim can't be reached or returns an error."""


def _normalize(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": result.get("display_name"),
        "name": result.get("name") or result.get("display_name"),
        "latitude": float(result["lat"]),
        "longitude": float(result["lon"]),
        "type": result.get("class"),
        "category": result.get("type"),
    }


async def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Look up `query` (an address, place name, or POI) via Nominatim."""
    params = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            response = await client.get(SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise NominatimError(f"Could not search for '{query}': {exc}") from exc

    return [_normalize(result) for result in data]


async def reverse(latitude: float, longitude: float) -> dict[str, Any] | None:
    """Reverse-geocode `latitude, longitude` to a place, or None if unmapped."""
    params = {"lat": latitude, "lon": longitude, "format": "jsonv2"}
    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            response = await client.get(REVERSE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise NominatimError(f"Could not reverse-geocode ({latitude}, {longitude}): {exc}") from exc

    if "error" in data:
        # Nominatim's "Unable to geocode" response for a real but unmapped
        # coordinate -- expected, not exceptional.
        return None
    return _normalize(data)
