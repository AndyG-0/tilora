from __future__ import annotations

import httpx
import pytest
import respx

from app.plugins.flights.aircraft import lookup_aircraft
from app.plugins.flights.airlines import lookup
from app.plugins.flights.plugin import (
    FlightsPlugin,
    _aircraft_kind,
    _airport_summary,
    _normalize,
    _parse_adsbdb_airport,
)

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
    respx.get(url__startswith="https://hexdb.io/api/v1/route/iata/").mock(return_value=httpx.Response(404))
    respx.get(url__startswith="https://hexdb.io/api/v1/airport/iata/").mock(return_value=httpx.Response(404))
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


def test_airport_summary_includes_null_coords_when_missing():
    assert _airport_summary({"iata": "DFW", "icao": "KDFW"})["latitude"] is None
    assert _airport_summary({"iata": "DFW", "icao": "KDFW"})["longitude"] is None


def test_parse_adsbdb_airport_includes_null_coords_when_missing():
    airport = _parse_adsbdb_airport({"iata_code": "DFW"})
    assert airport is not None
    assert airport["latitude"] is None
    assert airport["longitude"] is None


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
async def test_get_summary_caps_at_hundred():
    many = {"ac": [{**FAKE_RESPONSE["ac"][0], "hex": f"h{i}", "dst": float(i)} for i in range(120)]}
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=many))
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["count"] == 120
    assert len(summary["flights"]) == 100
    assert summary["truncated"] is True


@respx.mock
async def test_get_detail_caps_at_hundred():
    many = {"ac": [{**FAKE_RESPONSE["ac"][0], "hex": f"h{i}", "dst": float(i)} for i in range(120)]}
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=many))
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["count"] == 120
    assert len(detail["flights"]) == 100
    assert detail["truncated"] is True


@respx.mock
async def test_get_summary_not_truncated_under_cap():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["truncated"] is False


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
    # DFW->ORD is geographically plausible for UAL1698's fixture position
    # (33.4245, -97.9147), which sits right where a DFW departure climbing
    # out toward Chicago would be -- see test_flights_geo.py for the
    # underlying plausibility check this exercises.
    respx.get("https://api.adsbdb.com/v0/callsign/UAL1698").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "flightroute": {
                        "callsign": "UAL1698",
                        "origin": {
                            "iata_code": "DFW",
                            "icao_code": "KDFW",
                            "municipality": "Dallas-Fort Worth",
                            "name": "Dallas Fort Worth International Airport",
                            "latitude": 32.8998,
                            "longitude": -97.0403,
                        },
                        "destination": {
                            "iata_code": "ORD",
                            "icao_code": "KORD",
                            "municipality": "Chicago",
                            "name": "O'Hare International Airport",
                            "latitude": 41.9786,
                            "longitude": -87.9048,
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
    assert by_callsign["UAL1698"]["origin"] == {
        "iata": "DFW",
        "icao": "KDFW",
        "city": "Dallas-Fort Worth",
        "latitude": 32.8998,
        "longitude": -97.0403,
    }
    assert by_callsign["UAL1698"]["destination"] == {
        "iata": "ORD",
        "icao": "KORD",
        "city": "Chicago",
        "latitude": 41.9786,
        "longitude": -87.9048,
    }


@respx.mock
async def test_get_summary_suppresses_geographically_implausible_adsbdb_route():
    # Real-world bug case: ADSBDB is keyed purely by callsign with no sense
    # of "today's actual flight", so a reused flight number can resolve to a
    # route that has nothing to do with where the aircraft actually is (this
    # exact response was observed live for a Southwest flight cruising near
    # Phoenix, AZ). UAL1698's fixture position (33.4245, -97.9147) is near
    # Fort Worth, TX -- nowhere near either Denver or Nashville.
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
                            "iata_code": "DEN",
                            "icao_code": "KDEN",
                            "municipality": "Denver",
                            "latitude": 39.8617,
                            "longitude": -104.6731,
                        },
                        "destination": {
                            "iata_code": "BNA",
                            "icao_code": "KBNA",
                            "municipality": "Nashville",
                            "latitude": 36.1245,
                            "longitude": -86.6782,
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
    assert by_callsign["UAL1698"]["origin"] is None
    assert by_callsign["UAL1698"]["destination"] is None


@respx.mock
async def test_get_summary_falls_back_to_routeset_when_adsbdb_route_is_implausible():
    # When ADSBDB's route fails the plausibility check, it should be
    # treated the same as "not found" and fall through to adsb.lol's
    # routeset, rather than caching/returning the bad route.
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
                            "iata_code": "DEN",
                            "icao_code": "KDEN",
                            "municipality": "Denver",
                            "latitude": 39.8617,
                            "longitude": -104.6731,
                        },
                        "destination": {
                            "iata_code": "BNA",
                            "icao_code": "KBNA",
                            "municipality": "Nashville",
                            "latitude": 36.1245,
                            "longitude": -86.6782,
                        },
                    }
                }
            },
        )
    )
    mock_external_apis()
    mock_routeset(
        [
            {
                "callsign": "UAL1698",
                "plausible": True,
                "_airports": [
                    {"iata": "DFW", "icao": "KDFW", "location": "Dallas-Fort Worth", "lat": 32.8998, "lon": -97.0403},
                    {"iata": "ORD", "icao": "KORD", "location": "Chicago", "lat": 41.9786, "lon": -87.9048},
                ],
            }
        ]
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"] == {
        "iata": "DFW",
        "icao": "KDFW",
        "city": "Dallas-Fort Worth",
        "latitude": 32.8998,
        "longitude": -97.0403,
    }
    assert by_callsign["UAL1698"]["destination"] == {
        "iata": "ORD",
        "icao": "KORD",
        "city": "Chicago",
        "latitude": 41.9786,
        "longitude": -87.9048,
    }


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
                    {"iata": "DFW", "icao": "KDFW", "location": "Dallas-Fort Worth", "lat": 32.8998, "lon": -97.0403},
                    {"iata": "MDW", "icao": "KMDW", "location": "Chicago", "lat": 41.7868, "lon": -87.7522},
                ],
            }
        ]
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"] == {
        "iata": "DFW",
        "icao": "KDFW",
        "city": "Dallas-Fort Worth",
        "latitude": 32.8998,
        "longitude": -97.0403,
    }
    assert by_callsign["UAL1698"]["destination"] == {
        "iata": "MDW",
        "icao": "KMDW",
        "city": "Chicago",
        "latitude": 41.7868,
        "longitude": -87.7522,
    }


@respx.mock
async def test_get_summary_falls_back_to_hexdb_when_adsbdb_and_routeset_both_miss():
    # ADSBDB 404s (via mock_external_apis) and adsb.lol's routeset comes
    # back empty -- hexdb.io is the last resort. UAL1698's fixture position
    # (33.4245, -97.9147) is consistent with a DFW-MDW route.
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    respx.get("https://hexdb.io/api/v1/route/iata/UAL1698").mock(
        return_value=httpx.Response(200, json={"route": "DFW-MDW"})
    )
    respx.get("https://hexdb.io/api/v1/airport/iata/DFW").mock(
        return_value=httpx.Response(
            200, json={"iata": "DFW", "icao": "KDFW", "latitude": 32.8998, "longitude": -97.0403}
        )
    )
    respx.get("https://hexdb.io/api/v1/airport/iata/MDW").mock(
        return_value=httpx.Response(
            200, json={"iata": "MDW", "icao": "KMDW", "latitude": 41.7868, "longitude": -87.7522}
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"] == {
        "iata": "DFW",
        "icao": "KDFW",
        "city": None,
        "latitude": 32.8998,
        "longitude": -97.0403,
    }
    assert by_callsign["UAL1698"]["destination"] == {
        "iata": "MDW",
        "icao": "KMDW",
        "city": None,
        "latitude": 41.7868,
        "longitude": -87.7522,
    }


@respx.mock
async def test_get_summary_suppresses_geographically_implausible_hexdb_route():
    # Same real-world staleness problem as ADSBDB/routeset, but for hexdb.io:
    # a Denver-Nashville route makes no sense for an aircraft near Fort Worth.
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    respx.get("https://hexdb.io/api/v1/route/iata/UAL1698").mock(
        return_value=httpx.Response(200, json={"route": "DEN-BNA"})
    )
    respx.get("https://hexdb.io/api/v1/airport/iata/DEN").mock(
        return_value=httpx.Response(
            200, json={"iata": "DEN", "icao": "KDEN", "latitude": 39.8617, "longitude": -104.6731}
        )
    )
    respx.get("https://hexdb.io/api/v1/airport/iata/BNA").mock(
        return_value=httpx.Response(
            200, json={"iata": "BNA", "icao": "KBNA", "latitude": 36.1245, "longitude": -86.6782}
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"] is None
    assert by_callsign["UAL1698"]["destination"] is None


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


@respx.mock
async def test_hexdb_airport_lookup_is_cached_across_callsigns():
    # Two distinct callsigns whose hexdb routes both resolve through DFW/MDW
    # -- route lookups are cached per-callsign so both still hit hexdb.io's
    # route endpoint, but the airport cache is keyed by IATA code and should
    # be shared, so DFW/MDW are each looked up only once despite serving two
    # different flights in the same poll.
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    respx.get("https://hexdb.io/api/v1/route/iata/UAL1698").mock(
        return_value=httpx.Response(200, json={"route": "DFW-MDW"})
    )
    respx.get("https://hexdb.io/api/v1/route/iata/XYZ123").mock(
        return_value=httpx.Response(200, json={"route": "DFW-MDW"})
    )
    dfw_route = respx.get("https://hexdb.io/api/v1/airport/iata/DFW").mock(
        return_value=httpx.Response(
            200, json={"iata": "DFW", "icao": "KDFW", "latitude": 32.8998, "longitude": -97.0403}
        )
    )
    mdw_route = respx.get("https://hexdb.io/api/v1/airport/iata/MDW").mock(
        return_value=httpx.Response(
            200, json={"iata": "MDW", "icao": "KMDW", "latitude": 41.7868, "longitude": -87.7522}
        )
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()

    by_callsign = {f["callsign"]: f for f in summary["flights"]}
    assert by_callsign["UAL1698"]["origin"]["iata"] == "DFW"
    assert by_callsign["XYZ123"]["origin"]["iata"] == "DFW"
    assert dfw_route.calls.call_count == 1
    assert mdw_route.calls.call_count == 1


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


@respx.mock
async def test_get_summary_falls_back_to_empty_when_never_fetched_successfully():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        side_effect=httpx.ConnectTimeout("Connection timed out")
    )
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["count"] == 0
    assert summary["flights"] == []
    assert not summary["stale"]
    assert summary["fetched_at"] is None


@respx.mock
async def test_get_summary_falls_back_to_empty_on_fetch_http_error():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(503))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["count"] == 0
    assert summary["flights"] == []
    assert not summary["stale"]


@respx.mock
async def test_get_detail_falls_back_to_empty_on_fetch_http_error():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["count"] == 0
    assert detail["flights"] == []
    assert not detail["stale"]
    assert detail["fetched_at"] is None


@respx.mock
async def test_get_summary_falls_back_to_last_good_when_fetch_fails():
    route = respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    first = await plugin.get_summary()
    assert first["count"] == 3
    assert not first["stale"]

    route.side_effect = httpx.ConnectTimeout("Connection timed out")
    second = await plugin.get_summary()

    assert second["count"] == 3
    assert second["flights"] == first["flights"]
    assert second["stale"] is True
    assert second["fetched_at"] == first["fetched_at"]


@respx.mock
async def test_get_detail_falls_back_to_last_good_when_fetch_fails():
    route = respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    first = await plugin.get_detail()
    assert first["count"] == 3

    route.mock(return_value=httpx.Response(503))
    second = await plugin.get_detail()

    assert second["count"] == 3
    assert second["flights"] == first["flights"]
    assert second["stale"] is True
    assert second["fetched_at"] == first["fetched_at"]


@respx.mock
async def test_get_summary_clears_staleness_after_successful_refetch():
    route = respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    await plugin.get_summary()

    route.side_effect = httpx.ConnectTimeout("Connection timed out")
    stale = await plugin.get_summary()
    assert stale["stale"] is True

    route.mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    fresh = await plugin.get_summary()

    assert fresh["stale"] is False
    assert fresh["fetched_at"] != stale["fetched_at"]


def test_normalize_falls_back_to_registration_when_flight_is_missing_or_empty():
    ac_missing_flight = {"hex": "a06acc", "r": "N126JH", "t": "C172", "category": "A1"}
    normalized = _normalize(ac_missing_flight)
    assert normalized["callsign"] == "N126JH"
    assert normalized["registration"] == "N126JH"
    assert normalized["hex"] == "a06acc"

    ac_empty_flight = {"hex": "a06acc", "flight": "   ", "r": "N126JH", "t": "C172", "category": "A1"}
    normalized_empty = _normalize(ac_empty_flight)
    assert normalized_empty["callsign"] == "N126JH"


def test_normalize_falls_back_to_hex_when_flight_and_registration_are_missing():
    ac_hex_only = {"hex": "a06acc", "t": "C172", "category": "A1"}
    normalized = _normalize(ac_hex_only)
    assert normalized["callsign"] == "A06ACC"
    assert normalized["registration"] is None
    assert normalized["hex"] == "a06acc"


@respx.mock
async def test_get_summary_includes_aircraft_without_flight_callsigns():
    response = {
        "ac": [
            {
                "hex": "a00001",
                "r": "N100AA",
                "t": "C172",
                "category": "A1",
                "alt_baro": 3500,
                "dst": 2.1,
            },
            {
                "hex": "a00002",
                "t": "PA28",
                "category": "A1",
                "alt_baro": 4500,
                "dst": 4.5,
            },
        ]
    }
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(200, json=response))
    mock_external_apis()
    mock_routeset()
    plugin = make_plugin()

    summary = await plugin.get_summary()
    assert summary["count"] == 2
    assert summary["flights"][0]["callsign"] == "N100AA"
    assert summary["flights"][0]["hex"] == "a00001"
    assert summary["flights"][1]["callsign"] == "A00002"
    assert summary["flights"][1]["hex"] == "a00002"


@respx.mock
async def test_get_summary_handles_empty_routeset_response_gracefully():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    # adsb.lol returning 201 with an empty body (or invalid JSON)
    respx.post(ROUTESET_URL).mock(return_value=httpx.Response(201, text=""))
    plugin = make_plugin()

    summary = await plugin.get_summary()
    assert summary["count"] == 3
    assert len(summary["flights"]) == 3


@respx.mock
async def test_get_summary_handles_dict_routeset_response_gracefully():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    # adsb.lol returning an error dict rather than a list
    respx.post(ROUTESET_URL).mock(return_value=httpx.Response(200, json={"error": "Rate limit exceeded"}))
    plugin = make_plugin()

    summary = await plugin.get_summary()
    assert summary["count"] == 3
    assert len(summary["flights"]) == 3


@respx.mock
async def test_get_detail_handles_missing_settings_keys():
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    mock_external_apis()
    mock_routeset()
    # Plugin initialized with minimal settings missing lat/lon
    plugin = FlightsPlugin({"id": "flights", "settings": {}})

    detail = await plugin.get_detail()
    assert detail["latitude"] == 32.7555
    assert detail["longitude"] == -97.3308
    assert detail["radius_nm"] == 15
    assert detail["count"] == 3


@respx.mock
async def test_fetch_raises_and_logs_on_http_error(caplog: pytest.LogCaptureFixture):
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await plugin._fetch(client)

    assert "Could not fetch nearby flights from ADS-B feed" in caplog.text
    assert "HTTPStatusError" in caplog.text


@respx.mock
async def test_fetch_logs_exception_type_on_timeout_with_empty_str(caplog: pytest.LogCaptureFixture):
    respx.get(url__startswith="https://api.adsb.lol/v2/point/").mock(side_effect=httpx.ConnectTimeout(""))
    plugin = make_plugin()

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectTimeout):
            await plugin._fetch(client)

    assert "Could not fetch nearby flights from ADS-B feed for widget 'flights': ConnectTimeout" in caplog.text
