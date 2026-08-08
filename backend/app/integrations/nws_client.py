"""National Weather Service active-alerts client (api.weather.gov).

No API key required, but NWS's usage policy requires a descriptive
User-Agent identifying the application — requests without one may be
throttled or rejected. See
https://www.weather.gov/documentation/services-web-api
"""

from __future__ import annotations

from typing import Any

import httpx

ALERTS_URL = "https://api.weather.gov/alerts/active"

_HEADERS = {
    "User-Agent": "Tilora self-hosted dashboard (severe weather integration)",
    "Accept": "application/geo+json",
}


class NWSError(Exception):
    """Raised when the NWS alerts API can't be reached or returns an error."""


async def get_active_alerts(latitude: float, longitude: float) -> list[dict[str, Any]]:
    """Active NWS alerts covering `latitude, longitude`.

    NWS only covers the US — a location outside its coverage area just
    returns an empty list, not an error, so callers can poll unconditionally
    regardless of the configured location.
    """
    params = {"point": f"{latitude},{longitude}"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(ALERTS_URL, params=params, headers=_HEADERS)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise NWSError(f"Could not fetch NWS alerts: {exc}") from exc

    return [
        {
            "id": feature.get("properties", {}).get("id") or feature.get("id"),
            "event": feature.get("properties", {}).get("event"),
            "headline": feature.get("properties", {}).get("headline"),
            "severity": feature.get("properties", {}).get("severity"),
        }
        for feature in data.get("features", [])
    ]
