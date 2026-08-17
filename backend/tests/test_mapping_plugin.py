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

    assert {t.name for t in tools} == {
        "search_location",
        "get_directions",
        "find_nearby_places",
        "show_mapping_detail",
    }


async def test_get_ai_tools_names_are_suffixed_for_custom_instance():
    plugin = MappingPlugin({"id": "mapping-custom-1", "settings": dict(MappingPlugin.default_settings)})

    tools = plugin.get_ai_tools()

    assert {t.name for t in tools} == {
        "search_location_mapping_custom_1",
        "get_directions_mapping_custom_1",
        "find_nearby_places_mapping_custom_1",
        "show_mapping_detail_mapping_custom_1",
    }


async def test_show_mapping_detail_returns_widget_id_and_panel():
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    tool = tools["show_mapping_detail"]
    assert tool.is_navigation is True
    assert await tool.handler() == {"widget_id": plugin.id, "panel": None}
    assert await tool.handler(panel="directions") == {"widget_id": plugin.id, "panel": "directions"}
    assert await tool.handler(panel="nearby") == {"widget_id": plugin.id, "panel": "nearby"}


async def test_show_mapping_detail_includes_destination_and_origin_when_given():
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    tool = tools["show_mapping_detail"]
    assert await tool.handler(panel="directions", destination="Dallas, TX") == {
        "widget_id": plugin.id,
        "panel": "directions",
        "destination": "Dallas, TX",
    }
    assert await tool.handler(panel="directions", destination="Dallas, TX", origin="Austin, TX") == {
        "widget_id": plugin.id,
        "panel": "directions",
        "destination": "Dallas, TX",
        "origin": "Austin, TX",
    }


@respx.mock
async def test_get_directions_uses_plugin_settings_as_default_origin():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
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
async def test_get_directions_biases_destination_geocode_towards_origin():
    # Overpass has no match, so this falls through to Nominatim.
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_DEST_SEARCH))
    respx.get(url__startswith=OSRM_BASE_URL).mock(return_value=httpx.Response(200, json=FAKE_OSRM_RESPONSE))
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    await tools["get_directions"].handler(destination="Taco Bell")

    # Plugin settings (32.7555, -97.3308) are the default origin -- the
    # destination search should be biased towards them.
    params = search_route.calls.last.request.url.params
    assert params["q"] == "Taco Bell"
    assert params["viewbox"] == "-98.3308,33.7555,-96.3308,31.7555"


@respx.mock
async def test_get_directions_prefers_overpass_nearest_match_for_destination():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=FAKE_OVERPASS_RESPONSE))
    osrm_route = respx.get(url__startswith=OSRM_BASE_URL).mock(
        return_value=httpx.Response(200, json=FAKE_OSRM_RESPONSE)
    )
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    # No SEARCH_URL mock is registered -- if Nominatim were called for the
    # destination despite an Overpass match existing, respx would fail this
    # request since it would be unmocked.
    result = await tools["get_directions"].handler(destination="Test Cafe")

    assert result["destination"] == "Test Cafe"
    requested_path = osrm_route.calls.last.request.url.path
    assert "-97.3308,32.7555" in requested_path
    assert "-97.331,32.756" in requested_path


@respx.mock
async def test_search_location_biases_towards_default_origin():
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_DEST_SEARCH))
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    await tools["search_location"].handler(query="Taco Bell")

    params = search_route.calls.last.request.url.params
    assert params["viewbox"] == "-98.3308,33.7555,-96.3308,31.7555"


@respx.mock
async def test_get_directions_falls_back_to_user_preferences_location(monkeypatch):
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
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
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
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
