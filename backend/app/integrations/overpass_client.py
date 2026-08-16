"""Overpass API client for nearby-POI search (overpass-api.de/api/interpreter).

No API key required. `CATEGORY_TAGS` is the fixed category vocabulary shared
by the AI tool's JSON-Schema enum, the REST endpoint's validation, and the
frontend's category chips -- defined here since it's Overpass-tag knowledge,
not plugin or router knowledge.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx

BASE_URL = "https://overpass-api.de/api/interpreter"

_HEADERS = {"User-Agent": "Tilora self-hosted dashboard (mapping integration)"}

# The public overpass-api.de instance queues queries under load, so a 504 (or
# a dropped connection) on an otherwise-valid query is common and usually
# clears within a couple seconds -- worth a couple of retries before
# surfacing an error to the user.
_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 1.5

CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "bar": [("amenity", "bar"), ("amenity", "pub")],
    "grocery": [("shop", "supermarket"), ("shop", "convenience")],
    "gas_station": [("amenity", "fuel")],
    "pharmacy": [("amenity", "pharmacy")],
    "hospital": [("amenity", "hospital")],
    "atm_bank": [("amenity", "atm"), ("amenity", "bank")],
    "hotel": [("tourism", "hotel"), ("tourism", "motel")],
    "attraction": [("tourism", "attraction"), ("tourism", "museum"), ("tourism", "artwork")],
    "park": [("leisure", "park")],
}


class OverpassError(Exception):
    """Raised for an unknown category or when Overpass can't be reached."""


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def _build_query(lat: float, lon: float, tags: list[tuple[str, str]], radius_m: int, limit: int) -> str:
    clauses = "\n".join(
        f'  {kind}["{key}"="{value}"](around:{radius_m},{lat},{lon});'
        for key, value in tags
        for kind in ("node", "way")
    )
    return f"[out:json][timeout:15];\n(\n{clauses}\n);\nout center {limit};"


def _address(tags: dict[str, Any]) -> str | None:
    parts = [tags.get("addr:housenumber"), tags.get("addr:street")]
    street = " ".join(part for part in parts if part)
    return street or None


def _normalize(element: dict[str, Any], category: str, lat: float, lon: float) -> dict[str, Any] | None:
    tags = element.get("tags") or {}
    if element["type"] == "node":
        el_lat, el_lon = element.get("lat"), element.get("lon")
    else:
        center = element.get("center") or {}
        el_lat, el_lon = center.get("lat"), center.get("lon")
    if el_lat is None or el_lon is None or not tags.get("name"):
        return None
    return {
        "name": tags["name"],
        "category": category,
        "latitude": el_lat,
        "longitude": el_lon,
        "distance_m": _haversine_m(lat, lon, el_lat, el_lon),
        "address": _address(tags),
        # OSM has no review/rating data (that needs a paid API like Google
        # Places/Yelp, which this feature deliberately avoids) -- these
        # contact tags are the closest free substitute when present.
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "website": tags.get("website") or tags.get("contact:website"),
        "opening_hours": tags.get("opening_hours"),
    }


async def _post_with_retry(query: str, category: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                response = await client.post(BASE_URL, data={"data": query})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    raise OverpassError(f"Could not search for nearby {category}: {exc}") from exc
                await asyncio.sleep(_RETRY_DELAY_SECONDS * (attempt + 1))


async def nearby(lat: float, lon: float, category: str, radius_m: int = 40234, limit: int = 20) -> list[dict[str, Any]]:
    if category not in CATEGORY_TAGS:
        raise OverpassError(f"Unknown category '{category}'")

    query = _build_query(lat, lon, CATEGORY_TAGS[category], radius_m, limit)
    data = await _post_with_retry(query, category)

    results = [_normalize(element, category, lat, lon) for element in data.get("elements", [])]
    places = [result for result in results if result is not None]
    places.sort(key=lambda place: place["distance_m"])
    return places[:limit]
