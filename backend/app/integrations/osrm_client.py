"""OSRM directions client, against the public demo server (router.project-osrm.org).

No API key required. This is a best-effort public demo instance (not backed
by an SLA) -- acceptable here since every call is user/AI-triggered on
demand, never polled.
"""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://router.project-osrm.org"

_HEADERS = {"User-Agent": "Tilora self-hosted dashboard (mapping integration)"}

# OSRM profile names differ from the mode strings used throughout the rest of
# this feature (and shown to the user/AI).
_PROFILES = {"driving": "driving", "walking": "foot", "cycling": "bike"}


class OSRMError(Exception):
    """Raised when OSRM can't be reached, rejects the request, or finds no route."""


def _step_instruction(step: dict[str, Any]) -> str:
    maneuver = step.get("maneuver") or {}
    kind = maneuver.get("type") or "continue"
    modifier = maneuver.get("modifier")
    name = step.get("name") or ""

    if kind == "depart":
        return f"Head out{f' on {name}' if name else ''}"
    if kind == "arrive":
        return "Arrive at your destination"
    if kind in ("turn", "end of road", "fork", "ramp"):
        direction = modifier.replace("_", " ") if modifier else "onto"
        return f"Turn {direction}{f' onto {name}' if name else ''}"
    if kind == "roundabout":
        return f"Take the roundabout{f' onto {name}' if name else ''}"
    if kind == "merge":
        return f"Merge{f' onto {name}' if name else ''}"
    return f"Continue{f' onto {name}' if name else ''}"


async def route(origin: tuple[float, float], destination: tuple[float, float], mode: str = "driving") -> dict[str, Any]:
    """Route from `origin` to `destination`, both (latitude, longitude) pairs.

    OSRM's URL takes coordinates as `lon,lat` -- the opposite of every other
    lat/lon pair in this feature -- so the transposition happens right here,
    once, rather than at every call site.
    """
    if mode not in _PROFILES:
        raise OSRMError(f"Unknown travel mode '{mode}'")
    profile = _PROFILES[mode]
    o_lat, o_lon = origin
    d_lat, d_lon = destination
    url = f"{BASE_URL}/route/v1/{profile}/{o_lon},{o_lat};{d_lon},{d_lat}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}

    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise OSRMError(f"Could not fetch a route: {exc}") from exc

    if data.get("code") != "Ok":
        # OSRM returns HTTP 200 with a `code` field for logical errors (e.g.
        # NoRoute), not an HTTP error status.
        raise OSRMError(data.get("message") or f"OSRM returned '{data.get('code')}'")

    leg_route = data["routes"][0]
    steps: list[dict[str, Any]] = []
    for leg in leg_route.get("legs", []):
        for step in leg.get("steps", []):
            steps.append(
                {
                    "instruction": _step_instruction(step),
                    "distance_meters": step.get("distance", 0.0),
                    "duration_seconds": step.get("duration", 0.0),
                }
            )

    # GeoJSON coordinates are [lon, lat]; flip to [lat, lon] for Leaflet.
    geometry = [[lat, lon] for lon, lat in leg_route["geometry"]["coordinates"]]

    return {
        "distance_meters": leg_route["distance"],
        "duration_seconds": leg_route["duration"],
        "geometry": geometry,
        "steps": steps,
    }
