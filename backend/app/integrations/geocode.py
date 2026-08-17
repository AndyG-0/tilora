"""Shared "resolve a place name near a point" helper.

Used by both the directions REST endpoint (app.api.mapping) and the AI
assistant's mapping tools (app.plugins.mapping.plugin) so they never drift
apart -- see app.api.mapping's module docstring.

Prefers overpass_client.find_by_name's genuine nearest-first distance sort
over nominatim_client.search's relevance-ranked (not distance-ranked)
results whenever a bias point is available, so a chain-name destination
(e.g. "Taco Bell") resolves to the closest branch instead of whichever one
Nominatim considers most "important" -- which can be states away. Falls back
to Nominatim's own soft-viewbox-biased geocoding for anything Overpass has
no name match for (addresses, cities, and places untagged or tagged under a
different name).
"""

from __future__ import annotations

from typing import Any

from app.integrations import nominatim_client, overpass_client

#: Same default radius as find_nearby_places/overpass_client.nearby (25mi).
_OVERPASS_RADIUS_M = 40234


async def resolve_near(place: str, near: tuple[float, float] | None = None) -> dict[str, Any] | None:
    if near is not None:
        lat, lon = near
        try:
            matches = await overpass_client.find_by_name(lat, lon, place, radius_m=_OVERPASS_RADIUS_M, limit=1)
        except overpass_client.OverpassError:
            matches = []
        if matches:
            match = matches[0]
            return {"latitude": match["latitude"], "longitude": match["longitude"], "name": match["name"]}

    matches = await nominatim_client.search(place, limit=1, near=near)
    if not matches:
        return None
    match = matches[0]
    return {"latitude": match["latitude"], "longitude": match["longitude"], "name": match["name"]}
