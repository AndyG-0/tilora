from __future__ import annotations

import httpx
import respx

from app.integrations.nominatim_client import SEARCH_URL
from app.integrations.osrm_client import BASE_URL as OSRM_BASE_URL
from app.integrations.overpass_client import BASE_URL as OVERPASS_URL
from app.plugins.mapping.plugin import MappingPlugin

FAKE_ORIGIN_SEARCH = [
    {
        "display_name": "Fort Worth, Tarrant County, Texas, United States",
        "name": "Fort Worth",
        "lat": "32.7555",
        "lon": "-97.3308",
        "class": "place",
        "type": "city",
    }
]

FAKE_DEST_SEARCH = [
    {
        "display_name": "Dallas, Dallas County, Texas, United States",
        "name": "Dallas",
        "lat": "32.7767",
        "lon": "-96.7970",
        "class": "place",
        "type": "city",
    }
]

FAKE_OSRM_RESPONSE = {
    "code": "Ok",
    "routes": [
        {
            "distance": 50000.0,
            "duration": 2400.0,
            "geometry": {"coordinates": [[-97.3308, 32.7555], [-96.7970, 32.7767]]},
            "legs": [
                {"steps": [{"maneuver": {"type": "depart"}, "name": "I-30 E", "distance": 50000.0, "duration": 2400.0}]}
            ],
        }
    ],
}

FAKE_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "lat": 32.756,
            "lon": -97.331,
            "tags": {"name": "Test Cafe"},
        }
    ]
}


def make_plugin(settings: dict | None = None, user_id: str | None = None) -> MappingPlugin:
    return MappingPlugin(
        {
            "id": "mapping",
            "user_id": user_id,
            "settings": settings if settings is not None else dict(MappingPlugin.default_settings),
        }
    )


def test_settings_scope_is_personal():
    assert MappingPlugin.settings_scope == "personal"


async def test_get_summary_returns_home_location():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {"location_name": "Fort Worth, TX", "latitude": 32.7555, "longitude": -97.3308}


async def test_get_detail_matches_summary():
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()


async def test_get_ai_tools_names_are_unsuffixed_for_default_instance():
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert {t.name for t in tools} == {"search_location", "get_directions", "find_nearby_places"}


async def test_get_ai_tools_names_are_suffixed_for_custom_instance():
    plugin = MappingPlugin({"id": "mapping-custom-1", "settings": dict(MappingPlugin.default_settings)})

    tools = plugin.get_ai_tools()

    assert {t.name for t in tools} == {
        "search_location_mapping_custom_1",
        "get_directions_mapping_custom_1",
        "find_nearby_places_mapping_custom_1",
    }


@respx.mock
async def test_get_directions_uses_plugin_settings_as_default_origin():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_DEST_SEARCH))
    osrm_route = respx.get(url__startswith=OSRM_BASE_URL).mock(
        return_value=httpx.Response(200, json=FAKE_OSRM_RESPONSE)
    )
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["get_directions"].handler(destination="Dallas, TX")

    assert result["origin"] == "Fort Worth, TX"
    assert result["destination"] == "Dallas"
    assert result["distance_meters"] == 50000.0
    requested_path = osrm_route.calls.last.request.url.path
    assert "-97.3308,32.7555" in requested_path


@respx.mock
async def test_get_directions_falls_back_to_user_preferences_location(monkeypatch):
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_DEST_SEARCH))
    respx.get(url__startswith=OSRM_BASE_URL).mock(return_value=httpx.Response(200, json=FAKE_OSRM_RESPONSE))
    monkeypatch.setattr(
        "app.plugins.mapping.plugin.get_user_preferences",
        lambda user_id: {"location": {"latitude": 40.0, "longitude": -74.0, "display_name": "New York, NY"}},
    )
    plugin = make_plugin(settings={"latitude": None, "longitude": None, "location_name": None}, user_id="u1")
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["get_directions"].handler(destination="Dallas, TX")

    assert result["origin"] == "New York, NY"


@respx.mock
async def test_get_directions_returns_error_when_no_location_available():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_DEST_SEARCH))
    plugin = make_plugin(settings={"latitude": None, "longitude": None, "location_name": None})
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["get_directions"].handler(destination="Dallas, TX")

    assert "error" in result


@respx.mock
async def test_get_directions_returns_error_for_unresolvable_destination():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["get_directions"].handler(destination="Nowhereville")

    assert "error" in result


@respx.mock
async def test_find_nearby_places_uses_plugin_settings_as_default_point():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=FAKE_OVERPASS_RESPONSE))
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["find_nearby_places"].handler(category="cafe")

    assert result["near"] == "Fort Worth, TX"
    assert result["places"][0]["name"] == "Test Cafe"


async def test_find_nearby_places_returns_error_when_no_location_available():
    plugin = make_plugin(settings={"latitude": None, "longitude": None, "location_name": None})
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["find_nearby_places"].handler(category="cafe")

    assert "error" in result


@respx.mock
async def test_search_location_returns_matches():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_ORIGIN_SEARCH))
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["search_location"].handler(query="Fort Worth")

    assert result["matches"][0]["name"] == "Fort Worth"


@respx.mock
async def test_search_location_returns_error_for_no_matches():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["search_location"].handler(query="Nowhereville")

    assert "error" in result
