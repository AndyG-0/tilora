"""Flights plugin, backed by adsb.lol's public ADS-B feed (no API key required)."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from app.i18n import t
from app.plugins.base import Plugin, ToolDef
from app.plugins.flights.airlines import lookup

ADSB_URL = "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius_nm}"

_SUMMARY_CAP = 8
_DETAIL_CAP = 20


def _altitude_ft(ac: dict[str, Any]) -> int | float | None:
    # adsb.lol reports the literal string "ground" instead of a number for
    # aircraft that haven't taken off/have landed.
    alt = ac.get("alt_baro")
    return alt if isinstance(alt, int | float) else None


def _normalize(ac: dict[str, Any]) -> dict[str, Any]:
    callsign = (ac.get("flight") or "").strip()
    airline = lookup(callsign)
    return {
        "callsign": callsign,
        "airline_code": airline["airline_code"],
        "airline_name": airline["airline_name"],
        "airline_iata": airline["airline_iata"],
        "aircraft_type": ac.get("t"),
        "registration": ac.get("r"),
        "altitude_ft": _altitude_ft(ac),
        "speed_kts": ac.get("gs"),
        "heading": ac.get("track"),
        "distance_nm": ac.get("dst"),
        "direction": ac.get("dir"),
        "latitude": ac.get("lat"),
        "longitude": ac.get("lon"),
    }


class FlightsPlugin(Plugin):
    id = "flights"
    name = "Flights"
    # Aircraft move fast (a jet covers ~7nm/minute) so this needs to refresh
    # much more often than weather's 600s to feel "live".
    refresh_interval_seconds = 90
    # Each household member cares about aircraft near their own location,
    # not a shared one — see Plugin.settings_scope.
    settings_scope = "personal"
    # A flight list needs more room than a single grid cell to be readable.
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}
    # Same Fort Worth, TX default as the weather plugin, swapped out by the
    # user via the detail view's location search.
    default_settings: ClassVar[dict[str, Any]] = {
        "latitude": 32.7555,
        "longitude": -97.3308,
        "location_name": "Fort Worth, TX",
        "radius_nm": 15,
    }

    async def _fetch(self) -> list[dict[str, Any]]:
        settings = self.config["settings"]
        url = ADSB_URL.format(
            lat=settings["latitude"],
            lon=settings["longitude"],
            radius_nm=settings.get("radius_nm", 15),
        )
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json().get("ac") or []

    async def _nearby_flights(self) -> list[dict[str, Any]]:
        aircraft = await self._fetch()
        flights = [_normalize(ac) for ac in aircraft if ac.get("alt_baro") != "ground"]
        flights.sort(key=lambda f: f["distance_nm"] if f["distance_nm"] is not None else float("inf"))
        return flights

    async def get_summary(self) -> dict[str, Any]:
        settings = self.config["settings"]
        flights = await self._nearby_flights()
        return {
            "location_name": settings.get("location_name") or t("flights.your_location", self.locale),
            "radius_nm": settings.get("radius_nm", 15),
            "count": len(flights),
            "flights": flights[:_SUMMARY_CAP],
        }

    async def get_detail(self) -> dict[str, Any]:
        settings = self.config["settings"]
        flights = await self._nearby_flights()
        return {
            "location_name": settings.get("location_name") or t("flights.your_location", self.locale),
            "radius_nm": settings.get("radius_nm", 15),
            "count": len(flights),
            "flights": flights[:_DETAIL_CAP],
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_nearby_flights_summary() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_nearby_flights_summary",
                description="Get a summary of aircraft currently near the dashboard's configured location.",
                parameters={"type": "object", "properties": {}},
                handler=get_nearby_flights_summary,
            )
        ]
