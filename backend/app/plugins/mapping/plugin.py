"""Mapping plugin: location search, directions, and nearby-place search.

Backed entirely by free, keyless OpenStreetMap services (Nominatim, OSRM,
Overpass -- see app.integrations.{nominatim,osrm,overpass}_client). Unlike
most plugins, get_summary/get_detail only return the configured home
location: search/directions/nearby are on-demand, user- or AI-triggered
lookups served by app.api.mapping, not periodic poll data.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.integrations import geocode, nominatim_client, osrm_client, overpass_client
from app.integrations.overpass_client import CATEGORY_TAGS
from app.plugins.base import Plugin, ToolDef
from app.storage.cache import cached_call
from app.storage.db import get_user_preferences

_NO_LOCATION_ERROR = "No location is configured -- set a home location on the Mapping tile or in your profile."

# Same TTLs as app.api.mapping's REST endpoints -- Nominatim's usage policy
# explicitly asks callers to cache results rather than throttle client-side,
# and these AI tools previously called the integration clients directly with
# no caching at all.
_GEOCODE_TTL_SECONDS = 24 * 60 * 60
_DIRECTIONS_TTL_SECONDS = 10 * 60
_NEARBY_TTL_SECONDS = 30 * 60


class MappingPlugin(Plugin):
    id = "mapping"
    name = "Mapping"
    # Each household member has their own home location, like weather/flights.
    settings_scope = "personal"
    # Summary/detail are just the static home location -- nothing to poll.
    refresh_interval_seconds = 3600
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 1, "rowSpan": 1}
    # Same Fort Worth, TX default as weather/flights.
    default_settings: ClassVar[dict[str, Any]] = {
        "latitude": 32.7555,
        "longitude": -97.3308,
        "location_name": "Fort Worth, TX",
    }

    def _location_payload(self) -> dict[str, Any]:
        settings = self.config["settings"]
        return {
            "location_name": settings.get("location_name"),
            "latitude": settings.get("latitude"),
            "longitude": settings.get("longitude"),
        }

    async def get_summary(self) -> dict[str, Any]:
        return self._location_payload()

    async def get_detail(self) -> dict[str, Any]:
        return self._location_payload()

    def _default_origin(self) -> dict[str, Any] | None:
        """The best available fallback origin/"near me" point.

        Order: this tile's own configured home location first (the more
        deliberate, mapping-specific setting), then the household member's
        global location preference (the same field the AI's ambient
        location context reads -- see app.ai.assistant._build_system_prompt),
        then None if neither is available.
        """
        settings = self.config["settings"]
        if settings.get("latitude") is not None and settings.get("longitude") is not None:
            return {
                "latitude": settings["latitude"],
                "longitude": settings["longitude"],
                "name": settings.get("location_name"),
            }
        if self.requesting_user_id is not None:
            location = get_user_preferences(self.requesting_user_id).get("location")
            if location:
                return {
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "name": location["display_name"],
                }
        return None

    async def _resolve_point(self, place: str | None, near: tuple[float, float] | None = None) -> dict[str, Any] | None:
        """Resolve a free-text place to a point, falling back to the default
        origin when `place` is omitted.

        `near`, when given, biases the resolution towards that point -- see
        app.integrations.geocode.resolve_near.
        """
        if not place:
            return self._default_origin()
        return await geocode.resolve_near(place, near=near)

    def get_ai_tools(self) -> list[ToolDef]:
        async def search_location(query: str) -> dict[str, Any]:
            near_origin = self._default_origin()
            near = (near_origin["latitude"], near_origin["longitude"]) if near_origin else None

            async def fetch() -> list[dict[str, Any]]:
                return await nominatim_client.search(query, limit=5, near=near)

            key = f"mapping:ai_search:{query.lower()}:{near}"
            matches = await cached_call(key, _GEOCODE_TTL_SECONDS, fetch)
            if not matches:
                return {"error": f"Could not find a location for '{query}'."}
            return {"matches": matches}

        async def get_directions(destination: str, origin: str | None = None, mode: str = "driving") -> dict[str, Any]:
            async def fetch() -> dict[str, Any]:
                orig = await self._resolve_point(origin)
                if orig is None:
                    return {"error": _NO_LOCATION_ERROR if not origin else f"Could not find a location for '{origin}'."}
                dest = await self._resolve_point(destination, near=(orig["latitude"], orig["longitude"]))
                if dest is None:
                    return {"error": f"Could not find a location for '{destination}'."}
                try:
                    result = await osrm_client.route(
                        (orig["latitude"], orig["longitude"]), (dest["latitude"], dest["longitude"]), mode
                    )
                except osrm_client.OSRMError as exc:
                    return {"error": str(exc)}
                return {"origin": orig["name"], "destination": dest["name"], "mode": mode, **result}

            key = f"mapping:ai_directions:{mode}:{origin or ''}:{destination}"
            return await cached_call(key, _DIRECTIONS_TTL_SECONDS, fetch)

        async def show_mapping_detail(
            panel: str | None = None, destination: str | None = None, origin: str | None = None
        ) -> dict[str, Any]:
            result: dict[str, Any] = {"widget_id": self.id, "panel": panel}
            if destination:
                result["destination"] = destination
            if origin:
                result["origin"] = origin
            return result

        async def find_nearby_places(category: str, near: str | None = None, radius_m: int = 40234) -> dict[str, Any]:
            async def fetch() -> dict[str, Any]:
                point = await self._resolve_point(near)
                if point is None:
                    return {"error": _NO_LOCATION_ERROR if not near else f"Could not find a location for '{near}'."}
                try:
                    places = await overpass_client.nearby(point["latitude"], point["longitude"], category, radius_m)
                except overpass_client.OverpassError as exc:
                    return {"error": str(exc)}
                return {"near": point["name"], "category": category, "places": places}

            key = f"mapping:ai_nearby:{category}:{near or ''}:{radius_m}"
            return await cached_call(key, _NEARBY_TTL_SECONDS, fetch)

        suffix = "" if self.id == "mapping" else f"_{self.id.replace('-', '_')}"
        return [
            ToolDef(
                name=f"search_location{suffix}",
                description="Look up a place or address and return its coordinates and a human-readable name.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Place name or address to look up."}},
                    "required": ["query"],
                },
                handler=search_location,
            ),
            ToolDef(
                name=f"get_directions{suffix}",
                description=(
                    "Get driving/walking/cycling directions and travel time between two places. "
                    "Accepts place names or addresses, not just coordinates."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "destination": {"type": "string", "description": "Destination place name or address."},
                        "origin": {
                            "type": "string",
                            "description": (
                                "Starting place name or address. If omitted, uses the user's home/current location."
                            ),
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["driving", "walking", "cycling"],
                            "description": "Mode of travel.",
                            "default": "driving",
                        },
                    },
                    "required": ["destination"],
                },
                handler=get_directions,
            ),
            ToolDef(
                name=f"find_nearby_places{suffix}",
                description="Find nearby restaurants, cafes, gas stations, and other points of interest.",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": list(CATEGORY_TAGS),
                            "description": "Kind of place to search for.",
                        },
                        "near": {
                            "type": "string",
                            "description": (
                                "Place name or address to search near. "
                                "If omitted, uses the user's home/current location."
                            ),
                        },
                        "radius_m": {
                            "type": "integer",
                            "description": "Search radius in meters.",
                            "default": 40234,
                        },
                    },
                    "required": ["category"],
                },
                handler=find_nearby_places,
            ),
            ToolDef(
                name=f"show_mapping_detail{suffix}",
                description=(
                    "Bring up the Mapping tile's detail page on the user's screen, in addition to "
                    "answering in words. Pass panel='directions' when the user asks for directions or "
                    "navigation to a place, panel='nearby' when they ask for nearby restaurants, gas "
                    "stations, or other points of interest, or omit panel for a general map question. "
                    "When panel='directions', also pass destination (and origin, only if the user named a "
                    "starting point other than home) so the page opens with the same trip already filled in "
                    "-- use the same place names you passed to get_directions."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "panel": {
                            "type": "string",
                            "enum": ["directions", "nearby"],
                            "description": "Which panel to open. Omit for the tile's plain detail view.",
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination place name, when panel='directions'.",
                        },
                        "origin": {
                            "type": "string",
                            "description": (
                                "Starting place name, only if the user specified one other than home, "
                                "when panel='directions'."
                            ),
                        },
                    },
                },
                handler=show_mapping_detail,
                is_navigation=True,
            ),
        ]
