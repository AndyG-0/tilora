"""Flights plugin, backed by adsb.lol's public ADS-B feed (no API key required)."""

from __future__ import annotations

import asyncio
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
ADSBDB_CALLSIGN_URL = "https://api.adsbdb.com/v0/callsign/{callsign}"
ADSBDB_AIRCRAFT_URL = "https://api.adsbdb.com/v0/aircraft/{hex}"
PLANESPOTTERS_URL = "https://api.planespotters.net/pub/photos/reg/{reg}"

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

_PLANESPOTTERS_HEADERS = {
    "User-Agent": "TiloraDashboard/1.0 (+https://github.com/tilora/tilora; support@tilora.local)",
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
# hammering APIs every 90s poll for callsigns that are unlikely to ever have a filed route (most GA).

_PHOTO_CACHE_TTL_FOUND_SECONDS = 7 * 24 * 60 * 60  # 7 days — aircraft registration photos rarely change
_PHOTO_CACHE_TTL_NOT_FOUND_SECONDS = 24 * 60 * 60  # 24h — retry unfound photos after a day


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
    hex_code = (ac.get("hex") or "").strip().lower()
    return {
        "hex": hex_code or None,
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
        "photo_thumbnail_url": None,
        "photo_url": None,
        "photo_photographer": None,
        "photo_link": None,
    }


def _route_cache_key(callsign: str) -> str:
    return f"flights:route:{callsign}"


def _photo_cache_key(reg_or_hex: str) -> str:
    return f"flights:photo:{reg_or_hex.upper()}"


def _airport_summary(airport: dict[str, Any]) -> dict[str, Any]:
    return {"iata": airport.get("iata") or None, "icao": airport.get("icao"), "city": airport.get("location")}


def _parse_adsbdb_airport(airport: dict[str, Any] | None) -> dict[str, Any] | None:
    if not airport:
        return None
    iata = airport.get("iata_code") or airport.get("iata") or None
    icao = airport.get("icao_code") or airport.get("icao") or None
    if not icao and not iata:
        return None
    city = airport.get("municipality") or airport.get("city") or airport.get("name") or None
    return {"iata": iata, "icao": icao, "city": city}


def _parse_route(result: dict[str, Any]) -> dict[str, Any]:
    airports = result.get("_airports") or []
    if not result.get("plausible") or len(airports) < 2:
        return {"origin": None, "destination": None}
    # adsb.lol/tar1090 treat _airports[0] as origin and the last entry as
    # destination, which also covers the rare >2-entry "multihop" case.
    return {"origin": _airport_summary(airports[0]), "destination": _airport_summary(airports[-1])}


async def _fetch_single_adsbdb_route(client: httpx.AsyncClient, callsign: str) -> dict[str, Any] | None:
    try:
        url = ADSBDB_CALLSIGN_URL.format(callsign=callsign)
        resp = await client.get(url, headers=_HEADERS, timeout=4.0)
        if resp.status_code == 200:
            payload = resp.json().get("response", {}).get("flightroute", {})
            origin = _parse_adsbdb_airport(payload.get("origin"))
            destination = _parse_adsbdb_airport(payload.get("destination"))
            if origin and destination:
                return {"origin": origin, "destination": destination}
        elif resp.status_code == 404:
            return {"origin": None, "destination": None}
    except Exception as exc:
        logger.debug("ADSBDB lookup failed for %s: %s", callsign, exc)
    return None


async def _fetch_single_photo(
    client: httpx.AsyncClient,
    registration: str | None,
    hex_code: str | None,
) -> dict[str, Any]:
    # 1. Try Planespotters by registration
    if registration:
        try:
            url = PLANESPOTTERS_URL.format(reg=registration)
            resp = await client.get(url, headers=_PLANESPOTTERS_HEADERS, timeout=4.0)
            if resp.status_code == 200:
                photos = resp.json().get("photos") or []
                if photos:
                    first = photos[0]
                    thumb = first.get("thumbnail_large", {}).get("src") or first.get("thumbnail", {}).get("src")
                    if thumb:
                        return {
                            "photo_thumbnail_url": thumb,
                            "photo_url": first.get("link"),
                            "photo_photographer": first.get("photographer"),
                            "photo_link": first.get("link"),
                        }
        except Exception as exc:
            logger.debug("Planespotters lookup failed for %s: %s", registration, exc)

    # 2. Try ADSBDB aircraft endpoint by hex
    if hex_code:
        try:
            url = ADSBDB_AIRCRAFT_URL.format(hex=hex_code)
            resp = await client.get(url, headers=_HEADERS, timeout=4.0)
            if resp.status_code == 200:
                ac_data = resp.json().get("response", {}).get("aircraft", {})
                thumb = ac_data.get("url_photo_thumbnail") or ac_data.get("url_photo")
                if thumb:
                    return {
                        "photo_thumbnail_url": thumb,
                        "photo_url": ac_data.get("url_photo") or thumb,
                        "photo_photographer": None,
                        "photo_link": None,
                    }
        except Exception as exc:
            logger.debug("ADSBDB photo lookup failed for %s: %s", hex_code, exc)

    return {
        "photo_thumbnail_url": None,
        "photo_url": None,
        "photo_photographer": None,
        "photo_link": None,
    }


async def _fetch_routes(client: httpx.AsyncClient, flights: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Look up origin/destination for `flights`, keyed by callsign.

    Uses ADSBDB as primary route source with fallback to adsb.lol routeset.
    Cached per-callsign in the shared process-wide `cache` singleton.
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

    # 1. Query ADSBDB concurrently for all uncached callsigns
    adsbdb_tasks = [_fetch_single_adsbdb_route(client, plane["callsign"]) for plane in to_fetch]
    adsbdb_results = await asyncio.gather(*adsbdb_tasks, return_exceptions=True)

    unresolved_planes: list[dict[str, Any]] = []
    for plane, result in zip(to_fetch, adsbdb_results, strict=False):
        callsign = plane["callsign"]
        if isinstance(result, dict) and result.get("origin") and result.get("destination"):
            routes[callsign] = result
            cache.set(_route_cache_key(callsign), result, _ROUTE_CACHE_TTL_FOUND_SECONDS)
        else:
            unresolved_planes.append(plane)

    if not unresolved_planes:
        return routes

    # 2. Fallback to adsb.lol routeset for remaining unresolved planes
    try:
        response = await client.post(ROUTESET_URL, json={"planes": unresolved_planes}, headers=_HEADERS)
        response.raise_for_status()
        results = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Could not fetch flight routes from adsb.lol: %s", exc)
        results = []

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

    for plane in unresolved_planes:
        callsign = plane["callsign"]
        if callsign not in resolved:
            no_route = {"origin": None, "destination": None}
            routes[callsign] = no_route
            cache.set(_route_cache_key(callsign), no_route, _ROUTE_CACHE_TTL_NOT_FOUND_SECONDS)

    return routes


async def _fetch_photos(client: httpx.AsyncClient, flights: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Look up aircraft photos, keyed by registration or hex code."""
    photos: dict[str, dict[str, Any]] = {}
    to_fetch: list[dict[str, Any]] = []
    seen: set[str] = set()

    for flight in flights:
        key = flight.get("registration") or flight.get("hex")
        if not key or key in seen:
            continue
        seen.add(key)
        cached = cache.get(_photo_cache_key(key))
        if cached is not None:
            photos[key] = cached
        else:
            to_fetch.append({"key": key, "registration": flight.get("registration"), "hex": flight.get("hex")})

    if not to_fetch:
        return photos

    tasks = [_fetch_single_photo(client, item["registration"], item["hex"]) for item in to_fetch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for item, result in zip(to_fetch, results, strict=False):
        key = item["key"]
        if isinstance(result, dict) and result.get("photo_thumbnail_url"):
            photos[key] = result
            cache.set(_photo_cache_key(key), result, _PHOTO_CACHE_TTL_FOUND_SECONDS)
        else:
            no_photo = {
                "photo_thumbnail_url": None,
                "photo_url": None,
                "photo_photographer": None,
                "photo_link": None,
            }
            photos[key] = no_photo
            cache.set(_photo_cache_key(key), no_photo, _PHOTO_CACHE_TTL_NOT_FOUND_SECONDS)

    return photos


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
            # Never fetch routes or photos for aircraft beyond what either endpoint
            # ever displays, bounding the batch size even when radius_nm is large.
            target_slice = flights[:_DETAIL_CAP]
            routes, photos = await asyncio.gather(
                _fetch_routes(client, target_slice),
                _fetch_photos(client, target_slice),
            )
        for flight in flights:
            route = routes.get(flight["callsign"])
            if route is not None:
                flight["origin"], flight["destination"] = route["origin"], route["destination"]
            photo_key = flight.get("registration") or flight.get("hex")
            photo = photos.get(photo_key) if photo_key else None
            if photo is not None:
                flight["photo_thumbnail_url"] = photo.get("photo_thumbnail_url")
                flight["photo_url"] = photo.get("photo_url")
                flight["photo_photographer"] = photo.get("photo_photographer")
                flight["photo_link"] = photo.get("photo_link")
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
