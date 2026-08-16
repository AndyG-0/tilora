"""Location search, directions, and nearby-place lookup for the Mapping widget.

Backed by Nominatim/OSRM/Overpass (see app.integrations.*_client) -- no API
key required. These endpoints call the same integration-client functions the
MappingPlugin's AI tools use (app.plugins.mapping.plugin), so the REST API
and the AI assistant never drift apart on how a lookup is performed.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.integrations import nominatim_client, osrm_client, overpass_client
from app.integrations.overpass_client import CATEGORY_TAGS
from app.storage.cache import cached_call

router = APIRouter(prefix="/api/mapping", tags=["mapping"])

_GEOCODE_TTL_SECONDS = 24 * 60 * 60
_DIRECTIONS_TTL_SECONDS = 10 * 60
_NEARBY_TTL_SECONDS = 30 * 60


@router.get("/search")
async def search(q: str = Query(min_length=1)) -> list[dict[str, Any]]:
    return await cached_call(f"mapping:geocode:{q.lower()}", _GEOCODE_TTL_SECONDS, lambda: nominatim_client.search(q))


@router.get("/reverse")
async def reverse(lat: float, lon: float) -> dict[str, Any] | None:
    key = f"mapping:reverse:{round(lat, 4)}:{round(lon, 4)}"
    return await cached_call(key, _GEOCODE_TTL_SECONDS, lambda: nominatim_client.reverse(lat, lon))


async def _geocode_one(place: str) -> dict[str, Any] | None:
    matches = await nominatim_client.search(place, limit=1)
    return matches[0] if matches else None


async def _resolve_endpoint(name: str, lat: float | None, lon: float | None) -> dict[str, Any] | None:
    # The frontend already knows exact coordinates for the home location and
    # for a nearby-search result (from Overpass), so skip Nominatim geocoding
    # in those cases -- re-geocoding by name risks landing on a different,
    # same-named place (e.g. a different city's "Starbucks").
    if lat is not None and lon is not None:
        return {"name": name, "latitude": lat, "longitude": lon}
    return await _geocode_one(name)


def _geo_cache_key(name: str, lat: float | None, lon: float | None) -> str:
    if lat is not None and lon is not None:
        return f"{round(lat, 4)},{round(lon, 4)}"
    return name.lower()


@router.get("/directions")
async def directions(
    destination: str = Query(min_length=1),
    origin: str = Query(min_length=1),
    mode: str = Query("driving", pattern="^(driving|walking|cycling)$"),
    destination_lat: float | None = None,
    destination_lon: float | None = None,
    origin_lat: float | None = None,
    origin_lon: float | None = None,
) -> dict[str, Any]:
    async def fetch() -> dict[str, Any]:
        dest = await _resolve_endpoint(destination, destination_lat, destination_lon)
        if dest is None:
            raise HTTPException(404, f"Could not find a location for '{destination}'")
        orig = await _resolve_endpoint(origin, origin_lat, origin_lon)
        if orig is None:
            raise HTTPException(404, f"Could not find a location for '{origin}'")
        try:
            result = await osrm_client.route(
                (orig["latitude"], orig["longitude"]), (dest["latitude"], dest["longitude"]), mode
            )
        except osrm_client.OSRMError as exc:
            raise HTTPException(502, str(exc)) from exc
        return {"origin": orig["name"], "destination": dest["name"], "mode": mode, **result}

    origin_key = _geo_cache_key(origin, origin_lat, origin_lon)
    destination_key = _geo_cache_key(destination, destination_lat, destination_lon)
    key = f"mapping:directions:{mode}:{origin_key}:{destination_key}"
    return await cached_call(key, _DIRECTIONS_TTL_SECONDS, fetch)


@router.get("/nearby")
async def nearby(lat: float, lon: float, category: str, radius_m: int = 40234) -> list[dict[str, Any]]:
    if category not in CATEGORY_TAGS:
        raise HTTPException(400, f"Unknown category '{category}'")

    key = f"mapping:nearby:{category}:{round(lat, 3)}:{round(lon, 3)}:{radius_m}"

    async def fetch() -> list[dict[str, Any]]:
        try:
            return await overpass_client.nearby(lat, lon, category, radius_m)
        except overpass_client.OverpassError as exc:
            raise HTTPException(502, str(exc)) from exc

    return await cached_call(key, _NEARBY_TTL_SECONDS, fetch)
