"""Flights plugin, backed by adsb.lol's public ADS-B feed (no API key required)."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import httpx

from app.i18n import t
from app.plugins.base import Plugin, ToolDef
from app.plugins.flights.aircraft import lookup_aircraft
from app.plugins.flights.airlines import lookup
from app.storage.cache import cache

logger = logging.getLogger(__name__)

ADSB_URL = "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius_nm}"
ROUTESET_URL = "https://api.adsb.lol/api/0/routeset"

# adsb.lol's routeset endpoint silently returns a 201 with an empty body
# unless the request's Referer points at an adsb.lol-family site (confirmed
# live -- User-Agent turned out *not* to be the gate, despite looking like
# one). A browser-like User-Agent is sent too since it costs nothing and
# some deployments may check it, but Referer is the header that actually
# matters. Applied to every request this plugin makes, not just routeset,
# in case the point endpoint ever gets the same treatment.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://globe.adsb.lol/",
}

_SUMMARY_CAP = 8
_DETAIL_CAP = 20

# ADS-B emitter category -> our four-bucket aircraft classification. A2
# (15,500-75,000 lbs) is inherently ambiguous between a regional turboprop
# and a regional jet without a full aircraft-type database; bucketed as
# "jet" since regional jets are the more common case. No category at all
# (aircraft not broadcasting ADS-B v2 category) -> "unknown"; a known code
# outside these buckets (glider, balloon, UAV, ground vehicle, ...) ->
# "other".
_CATEGORY_KIND: dict[str, str] = {
    "A1": "prop",
    "A2": "jet",
    "A3": "jet",
    "A4": "jet",
    "A5": "jet",
    "A6": "jet",
    "A7": "helicopter",
}

_ROUTE_CACHE_TTL_FOUND_SECONDS = 6 * 60 * 60  # 6h — matches tar1090's own route-cache lifetime
_ROUTE_CACHE_TTL_NOT_FOUND_SECONDS = 30 * 60  # 30min — retry routeless flights periodically without
# hammering adsb.lol every 90s poll for callsigns that are unlikely to ever have a filed route (most GA).


def _altitude_ft(ac: dict[str, Any]) -> int | float | None:
    # adsb.lol reports the literal string "ground" instead of a number for
    # aircraft that haven't taken off/have landed.
    alt = ac.get("alt_baro")
    return alt if isinstance(alt, int | float) else None


def _aircraft_kind(category: str | None) -> str:
    """Classify helicopter/jet/prop/other/unknown from the ADS-B emitter
    category code alone -- see `_CATEGORY_KIND` for the accepted trade-offs.
    """
    if not category:
        return "unknown"
    return _CATEGORY_KIND.get(category.upper(), "other")


def _normalize(ac: dict[str, Any]) -> dict[str, Any]:
    callsign = (ac.get("flight") or "").strip()
    airline = lookup(callsign)
    aircraft = lookup_aircraft(ac.get("t"))
    category = ac.get("category")
    return {
        "callsign": callsign,
        "airline_code": airline["airline_code"],
        "airline_name": airline["airline_name"],
        "airline_iata": airline["airline_iata"],
        "aircraft_type": ac.get("t"),
        "aircraft_name": aircraft["name"],
        "aircraft_kind": _aircraft_kind(category),
        "category": category,
        "registration": ac.get("r"),
        "altitude_ft": _altitude_ft(ac),
        "speed_kts": ac.get("gs"),
        "heading": ac.get("track"),
        "distance_nm": ac.get("dst"),
        "direction": ac.get("dir"),
        "latitude": ac.get("lat"),
        "longitude": ac.get("lon"),
        "origin": None,
        "destination": None,
    }


def _route_cache_key(callsign: str) -> str:
    return f"flights:route:{callsign}"


def _airport_summary(airport: dict[str, Any]) -> dict[str, Any]:
    return {"iata": airport.get("iata") or None, "icao": airport.get("icao"), "city": airport.get("location")}


def _parse_route(result: dict[str, Any]) -> dict[str, Any]:
    airports = result.get("_airports") or []
    if not result.get("plausible") or len(airports) < 2:
        return {"origin": None, "destination": None}
    # adsb.lol/tar1090 treat _airports[0] as origin and the last entry as
    # destination, which also covers the rare >2-entry "multihop" case.
    return {"origin": _airport_summary(airports[0]), "destination": _airport_summary(airports[-1])}


async def _fetch_routes(client: httpx.AsyncClient, flights: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Look up origin/destination for `flights`, keyed by callsign.

    Cached per-callsign in the shared process-wide `cache` singleton, not
    instance state -- `Plugin.with_settings()` builds a fresh FlightsPlugin
    instance per personalized request (this plugin is settings_scope
    "personal"), so anything stored on `self` would never survive between
    polls. A negative "no route" result is cached too (shorter TTL) using an
    explicit sentinel dict rather than storing `None`, since `cache.get()`
    returns `None` for both "not cached" and a stored `None` value.
    """
    routes: dict[str, dict[str, Any]] = {}
    to_fetch: list[dict[str, Any]] = []
    seen: set[str] = set()
    for flight in flights:
        callsign = flight["callsign"]
        if not callsign or callsign in seen:
            continue
        seen.add(callsign)
        cached = cache.get(_route_cache_key(callsign))
        if cached is not None:
            routes[callsign] = cached
        elif flight["latitude"] is not None and flight["longitude"] is not None:
            to_fetch.append({"callsign": callsign, "lat": flight["latitude"], "lng": flight["longitude"]})

    if not to_fetch:
        return routes

    try:
        response = await client.post(ROUTESET_URL, json={"planes": to_fetch})
        response.raise_for_status()
        results = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Could not fetch flight routes: %s", exc)
        return routes  # uncached callsigns just have no route this poll; retried next poll

    resolved: set[str] = set()
    for result in results:
        callsign = (result.get("callsign") or "").strip()
        if not callsign:
            continue
        route = _parse_route(result)
        routes[callsign] = route
        resolved.add(callsign)
        ttl = _ROUTE_CACHE_TTL_FOUND_SECONDS if route["origin"] else _ROUTE_CACHE_TTL_NOT_FOUND_SECONDS
        cache.set(_route_cache_key(callsign), route, ttl)

    # adsb.lol may drop invalid/unmatched callsigns from the response
    # entirely -- treat those as "no route" too so they aren't re-POSTed
    # every poll.
    for plane in to_fetch:
        if plane["callsign"] not in resolved:
            no_route = {"origin": None, "destination": None}
            routes[plane["callsign"]] = no_route
            cache.set(_route_cache_key(plane["callsign"]), no_route, _ROUTE_CACHE_TTL_NOT_FOUND_SECONDS)

    return routes


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
        "speed_unit": "mph",
    }

    async def _fetch(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        settings = self.config["settings"]
        url = ADSB_URL.format(
            lat=settings["latitude"],
            lon=settings["longitude"],
            radius_nm=settings.get("radius_nm", 15),
        )
        response = await client.get(url)
        response.raise_for_status()
        return response.json().get("ac") or []

    async def _nearby_flights(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            aircraft = await self._fetch(client)
            flights = [_normalize(ac) for ac in aircraft if ac.get("alt_baro") != "ground"]
            flights.sort(key=lambda f: f["distance_nm"] if f["distance_nm"] is not None else float("inf"))
            # Never fetch routes for aircraft beyond what either endpoint
            # ever displays, bounding the POST batch size even when
            # radius_nm is large and many aircraft are in range.
            routes = await _fetch_routes(client, flights[:_DETAIL_CAP])
        for flight in flights:
            route = routes.get(flight["callsign"])
            if route is not None:
                flight["origin"], flight["destination"] = route["origin"], route["destination"]
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
            "latitude": settings["latitude"],
            "longitude": settings["longitude"],
            "radius_nm": settings.get("radius_nm", 15),
            "speed_unit": settings.get("speed_unit", "mph"),
            "count": len(flights),
            "flights": flights[:_DETAIL_CAP],
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_nearby_flights_summary() -> dict[str, Any]:
            return await self.get_summary()

        tool_name = (
            "get_nearby_flights_summary"
            if self.id == "flights"
            else f"get_nearby_flights_summary_{self.id.replace('-', '_')}"
        )
        location_name = self.config["settings"].get("location_name")
        desc = (
            f"Get a summary of aircraft currently near {location_name}."
            if location_name
            else "Get a summary of aircraft currently near the dashboard's configured location."
        )
        return [
            ToolDef(
                name=tool_name,
                description=desc,
                parameters={"type": "object", "properties": {}},
                handler=get_nearby_flights_summary,
            )
        ]
