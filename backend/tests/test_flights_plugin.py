from __future__ import annotations

import httpx
import respx

from app.plugins.flights.aircraft import lookup_aircraft
from app.plugins.flights.airlines import lookup
from app.plugins.flights.plugin import FlightsPlugin, _aircraft_kind

FAKE_RESPONSE = {
    "ac": [
        {
            "hex": "a5cc13",
            "flight": "UAL1698 ",
            "r": "N47282",
            "t": "B38M",
            "category": "A3",
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
            "category": "A1",
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
            "category": "A2",
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
            "category": "A5",
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

ROUTESET_URL = "https://api.adsb.lol/api/0/routeset"


def mock_routeset(response_json: list[dict] | None = None) -> respx.Route:
    return respx.post(ROUTESET_URL).mock(return_value=httpx.Response(200, json=response_json or []))


def mock_external_apis():
    respx.get(url__startswith="https://api.adsbdb.com/v0/callsign/").mock(return_value=httpx.Response(404))
    respx.get(url__startswith="https://api.adsbdb.com/v0/aircraft/").mock(return_value=httpx.Response(404))
    respx.get(url__startswith="https://api.planespotters.net/pub/photos/reg/").mock(
        return_value=httpx.Response(200, json={"photos": []})
    )


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


def test_lookup_matches_expanded_airlines():
    assert lookup("RYR123") == {"airline_code": "RYR", "airline_name": "Ryanair", "airline_iata": "FR"}
    assert lookup("UAE456") == {"airline_code": "UAE", "airline_name": "Emirates", "airline_iata": "EK"}
    assert lookup("GTI789") == {"airline_code": "GTI", "airline_name": "Atlas Air", "airline_iata": "5Y"}
    assert lookup("ENY100") == {"airline_code": "ENY", "airline_name": "Envoy Air", "airline_iata": "MQ"}


def test_lookup_aircraft_matches_known_types():
    assert lookup_aircraft("B738") == {"name": "Boeing 737-800", "manufacturer": "Boeing", "model": "737-800"}
    assert lookup_aircraft("B38M") == {"name": "Boeing 737 MAX 8", "manufacturer": "Boeing", "model": "737 MAX 8"}
    assert lookup_aircraft("C172") == {"name": "Cessna 172 Skyhawk", "manufacturer": "Cessna", "model": "172 Skyhawk"}
    assert lookup_aircraft("A321") == {"name": "Airbus A321", "manufacturer": "Airbus", "model": "A321"}
    assert lookup_aircraft("EC35") == {
        "name": "Airbus Helicopters H135 / EC135",
        "manufacturer": "Airbus Helicopters",
        "model": "H135",
    }


def test_lookup_aircraft_returns_none_for_unmapped_or_empty():
    assert lookup_aircraft("ZZZZ") == {"name": None, "manufacturer": None, "model": None}
    assert lookup_aircraft(None) == {"name": None, "manufacturer": None, "model": None}
    assert lookup_aircraft("") == {"name": None, "manufacturer": None, "model": None}


def test_aircraft_kind_classifies_rotorcraft_as_helicopter():
    assert _aircraft_kind("A7") == "helicopter"


def test_aircraft_kind_classifies_light_as_prop():
    assert _aircraft_kind("A1") == "prop"


def test_aircraft_kind_classifies_large_and_regional_as_jet():
    assert _aircraft_kind("A3") == "jet"
    assert _aircraft_kind("A5") == "jet"
    # A2 is inherently ambiguous (regional turboprop vs. regional jet) —
    # bucketed as jet, an accepted trade-off of the category-only approach.
    assert _aircraft_kind("A2") == "jet"


def test_aircraft_kind_classifies_unmapped_known_code_as_other():
    assert _aircraft_kind("B2") == "other"
    assert _aircraft_kind("C0") == "other"


def test_aircraft_kind_classifies_missing_category_as_unknown():
    assert _aircraft_kind(None) == "unknown"
    assert _aircraft_kind("") == "unknown"


@respx.mock
async def test_get_summary_excludes_ground_traffic():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
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
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    distances = [f["distance_nm"] for f in summary["flights"]]
    assert distances == sorted(distances)


@respx.mock
async def test_get_summary_maps_airline_fields():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["airline_name"] == "United Airlines"
    assert by_callsign["XYZ123"]["airline_name"] is None
    assert by_callsign["XYZ123"]["airline_code"] == "XYZ"


@respx.mock
async def test_get_summary_maps_aircraft_kind():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["aircraft_kind"] == "jet"
    assert by_callsign["N126JH"]["aircraft_kind"] == "prop"
    assert by_callsign["XYZ123"]["aircraft_kind"] == "jet"


@respx.mock
async def test_get_summary_caps_at_eight():
    many = {"ac": [{**FAKE_RESPONSE["ac"][0], "hex": f"h{i}", "dst": float(i)} for i in range(12)]}
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=many))
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["count"] == 12
    assert len(summary["flights"]) == 8


@respx.mock
async def test_get_detail_caps_at_twenty():
    many = {"ac": [{**FAKE_RESPONSE["ac"][0], "hex": f"h{i}", "dst": float(i)} for i in range(25)]}
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=many))
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["count"] == 25
    assert len(detail["flights"]) == 20


@respx.mock
async def test_get_detail_includes_configured_coordinates():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["latitude"] == 32.7555
    assert detail["longitude"] == -97.3308
    assert detail["speed_unit"] == "mph"


@respx.mock
async def test_get_summary_maps_aircraft_name():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["aircraft_name"] == "Boeing 737 MAX 8"
    assert by_callsign["XYZ123"]["aircraft_name"] == "Airbus A320"


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
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_nearby_flights_summary"
    result = await tools[0].handler()
    assert result["count"] == 3


@respx.mock
async def test_get_summary_includes_route_from_adsbdb():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    respx.get("https://api.adsbdb.com/v0/callsign/UAL1698").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "flightroute": {
                        "callsign": "UAL1698",
                        "origin": {
                            "iata_code": "ABQ",
                            "icao_code": "KABQ",
                            "municipality": "Albuquerque",
                            "name": "Albuquerque International Sunport",
                        },
                        "destination": {
                            "iata_code": "IAH",
                            "icao_code": "KIAH",
                            "municipality": "Houston",
                            "name": "George Bush Intercontinental Airport",
                        },
                    }
                }
            },
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"] == {"iata": "ABQ", "icao": "KABQ", "city": "Albuquerque"}
    assert by_callsign["UAL1698"]["destination"] == {"iata": "IAH", "icao": "KIAH", "city": "Houston"}


@respx.mock
async def test_get_summary_falls_back_to_routeset_when_adsbdb_missing():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset(
        [
            {
                "callsign": "UAL1698",
                "plausible": True,
                "_airports": [
                    {"iata": "ABQ", "icao": "KABQ", "location": "Albuquerque"},
                    {"iata": "HOU", "icao": "KHOU", "location": "Houston"},
                ],
            }
        ]
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"] == {"iata": "ABQ", "icao": "KABQ", "city": "Albuquerque"}
    assert by_callsign["UAL1698"]["destination"] == {"iata": "HOU", "icao": "KHOU", "city": "Houston"}


@respx.mock
async def test_get_summary_includes_photo_from_planespotters():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    respx.get("https://api.planespotters.net/pub/photos/reg/N47282").mock(
        return_value=httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "id": "12345",
                        "thumbnail_large": {"src": "https://example.com/n47282_large.jpg"},
                        "link": "https://www.planespotters.net/photo/12345/n47282",
                        "photographer": "Jane Doe",
                    }
                ]
            },
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["photo_thumbnail_url"] == "https://example.com/n47282_large.jpg"
    assert by_callsign["UAL1698"]["photo_photographer"] == "Jane Doe"


@respx.mock
async def test_get_summary_falls_back_to_adsbdb_aircraft_photo():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    respx.get("https://api.planespotters.net/pub/photos/reg/N47282").mock(
        return_value=httpx.Response(200, json={"photos": []})
    )
    respx.get("https://api.adsbdb.com/v0/aircraft/a5cc13").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "aircraft": {
                        "url_photo_thumbnail": "https://airport-data.com/thumb.jpg",
                        "url_photo": "https://airport-data.com/full.jpg",
                    }
                }
            },
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["photo_thumbnail_url"] == "https://airport-data.com/thumb.jpg"


@respx.mock
async def test_route_lookup_is_cached_between_polls():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    adsbdb_route = respx.get("https://api.adsbdb.com/v0/callsign/UAL1698").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "flightroute": {
                        "callsign": "UAL1698",
                        "origin": {"iata_code": "ABQ", "icao_code": "KABQ", "municipality": "Albuquerque"},
                        "destination": {"iata_code": "HOU", "icao_code": "KHOU", "municipality": "Houston"},
                    }
                }
            },
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    await plugin.get_summary()
    await plugin.get_summary()

    assert adsbdb_route.calls.call_count == 1


def test_get_ai_tools_default_and_custom_instances():
    default_plugin = FlightsPlugin({"id": "flights", "settings": {"location_name": "Austin, TX"}})
    default_tools = default_plugin.get_ai_tools()
    assert len(default_tools) == 1
    assert default_tools[0].name == "get_nearby_flights_summary"
    assert "Austin, TX" in default_tools[0].description

    custom_plugin = FlightsPlugin({"id": "flights-custom-123", "settings": {"location_name": "London, UK"}})
    custom_tools = custom_plugin.get_ai_tools()
    assert len(custom_tools) == 1
    assert custom_tools[0].name == "get_nearby_flights_summary_flights_custom_123"
    assert "London, UK" in custom_tools[0].description
