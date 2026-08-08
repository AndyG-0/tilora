from __future__ import annotations

import httpx
import respx

from app.plugins.flights.airlines import lookup
from app.plugins.flights.plugin import FlightsPlugin

FAKE_RESPONSE = {
    "ac": [
        {
            "hex": "a5cc13",
            "flight": "UAL1698 ",
            "r": "N47282",
            "t": "B38M",
            "alt_baro": 36000,
            "gs": 460.3,
            "track": 314.91,
            "lat": 33.4245,
            "lon": -97.9147,
            "dst": 49.762,
            "dir": 324.0,
        },
        {
            "hex": "a06acc",
            "flight": "N126JH  ",
            "r": "N126JH",
            "t": "BE20",
            "alt_baro": 25000,
            "gs": 277.0,
            "track": 71.04,
            "lat": 33.2354,
            "lon": -97.8199,
            "dst": 37.893,
            "dir": 319.6,
        },
        {
            "hex": "b00000",
            "flight": "XYZ123  ",
            "r": "N999XX",
            "t": "A320",
            "alt_baro": 10000,
            "gs": 200.0,
            "track": 90.0,
            "lat": 32.9,
            "lon": -97.4,
            "dst": 10.0,
            "dir": 90.0,
        },
        {
            "hex": "c00000",
            "flight": "DAL500  ",
            "r": "N500DL",
            "t": "B739",
            "alt_baro": "ground",
            "gs": 0.0,
            "track": 0.0,
            "lat": 32.75,
            "lon": -97.33,
            "dst": 0.5,
            "dir": 0.0,
        },
    ]
}


def make_plugin() -> FlightsPlugin:
    return FlightsPlugin(
        {
            "id": "flights",
            "settings": {
                "latitude": 32.7555,
                "longitude": -97.3308,
                "location_name": "Fort Worth, TX",
                "radius_nm": 15,
            },
        }
    )


def test_settings_scope_is_personal():
    # Each household member cares about aircraft near their own location.
    assert FlightsPlugin.settings_scope == "personal"


def test_lookup_matches_known_airline():
    result = lookup("UAL1698")
    assert result == {"airline_code": "UAL", "airline_name": "United Airlines", "airline_iata": "UA"}


def test_lookup_returns_code_only_for_unmapped_prefix():
    result = lookup("XYZ123")
    assert result == {"airline_code": "XYZ", "airline_name": None, "airline_iata": None}


def test_lookup_returns_none_for_tail_number_callsign():
    result = lookup("N583CA")
    assert result == {"airline_code": None, "airline_name": None, "airline_iata": None}


@respx.mock
async def test_get_summary_excludes_ground_traffic():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    callsigns = [f["callsign"] for f in summary["flights"]]
    assert "DAL500" not in callsigns
    assert summary["count"] == 3


@respx.mock
async def test_get_summary_sorts_nearest_first():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    distances = [f["distance_nm"] for f in summary["flights"]]
    assert distances == sorted(distances)


@respx.mock
async def test_get_summary_maps_airline_fields():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["airline_name"] == "United Airlines"
    assert by_callsign["XYZ123"]["airline_name"] is None
    assert by_callsign["XYZ123"]["airline_code"] == "XYZ"


@respx.mock
async def test_get_summary_caps_at_eight():
    many = {"ac": [{**FAKE_RESPONSE["ac"][0], "hex": f"h{i}", "dst": float(i)} for i in range(12)]}
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=many))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["count"] == 12
    assert len(summary["flights"]) == 8


@respx.mock
async def test_get_detail_caps_at_twenty():
    many = {"ac": [{**FAKE_RESPONSE["ac"][0], "hex": f"h{i}", "dst": float(i)} for i in range(25)]}
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=many))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["count"] == 25
    assert len(detail["flights"]) == 20


@respx.mock
async def test_fetch_uses_configured_coordinates_and_radius():
    route = respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json={"ac": []})
    )
    plugin = FlightsPlugin({"id": "flights", "settings": {"latitude": 40.0, "longitude": -74.0, "radius_nm": 25}})

    await plugin.get_summary()

    assert route.calls.last.request.url.path == "/v2/point/40.0/-74.0/25"


@respx.mock
async def test_get_ai_tools_exposes_flights_summary_tool():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_nearby_flights_summary"
    result = await tools[0].handler()
    assert result["count"] == 3
