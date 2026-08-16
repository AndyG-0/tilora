from __future__ import annotations

import httpx
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import mapping
from app.integrations.nominatim_client import REVERSE_URL, SEARCH_URL
from app.integrations.osrm_client import BASE_URL as OSRM_BASE_URL
from app.integrations.overpass_client import BASE_URL as OVERPASS_URL
from app.storage.cache import cache

FAKE_SEARCH_RESPONSE = [
    {
        "display_name": "Fort Worth, Tarrant County, Texas, United States",
        "name": "Fort Worth",
        "lat": "32.7555",
        "lon": "-97.3308",
        "class": "place",
        "type": "city",
    }
]

FAKE_DESTINATION_RESPONSE = [
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
                {
                    "steps": [
                        {
                            "maneuver": {"type": "depart"},
                            "name": "I-30 E",
                            "distance": 50000.0,
                            "duration": 2400.0,
                        }
                    ]
                }
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
            "tags": {"name": "Test Cafe", "addr:housenumber": "100", "addr:street": "Main St"},
        },
        {
            "type": "way",
            "center": {"lat": 32.760, "lon": -97.335},
            "tags": {"name": "Big Cafe"},
        },
    ]
}


async def _no_sleep(*args, **kwargs) -> None:
    return None


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(mapping.router)
    return TestClient(app)


@respx.mock
def test_search_returns_normalized_results():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_SEARCH_RESPONSE))
    client = make_client()

    response = client.get("/api/mapping/search", params={"q": "Fort Worth"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "display_name": "Fort Worth, Tarrant County, Texas, United States",
            "name": "Fort Worth",
            "latitude": 32.7555,
            "longitude": -97.3308,
            "type": "place",
            "category": "city",
        }
    ]


def test_search_requires_query_param():
    client = make_client()

    response = client.get("/api/mapping/search")

    assert response.status_code == 422


@respx.mock
def test_reverse_returns_none_when_unmapped():
    respx.get(REVERSE_URL).mock(return_value=httpx.Response(200, json={"error": "Unable to geocode"}))
    client = make_client()

    response = client.get("/api/mapping/reverse", params={"lat": 0.0, "lon": 0.0})

    assert response.status_code == 200
    assert response.json() is None


@respx.mock
def test_directions_calls_osrm_with_lon_lat_order():
    respx.get(SEARCH_URL).mock(
        # The router geocodes destination before origin -- see
        # app.api.mapping.directions().
        side_effect=[
            httpx.Response(200, json=FAKE_DESTINATION_RESPONSE),
            httpx.Response(200, json=FAKE_SEARCH_RESPONSE),
        ]
    )
    osrm_route = respx.get(url__startswith=OSRM_BASE_URL).mock(
        return_value=httpx.Response(200, json=FAKE_OSRM_RESPONSE)
    )
    client = make_client()

    response = client.get(
        "/api/mapping/directions",
        params={"origin": "Fort Worth, TX", "destination": "Dallas, TX", "mode": "driving"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["distance_meters"] == 50000.0
    assert body["origin"] == "Fort Worth"
    assert body["destination"] == "Dallas"

    # OSRM takes lon,lat order -- assert the request wasn't transposed.
    requested_path = osrm_route.calls.last.request.url.path
    assert "-97.3308,32.7555" in requested_path
    assert "-96.797,32.7767" in requested_path


@respx.mock
def test_directions_uses_provided_coordinates_and_skips_geocoding():
    # No SEARCH_URL mock is registered -- if the endpoint geocoded either
    # side despite having exact coordinates (e.g. from a nearby-search
    # result or the configured home location), respx would fail the test
    # since that request would be unmocked.
    osrm_route = respx.get(url__startswith=OSRM_BASE_URL).mock(
        return_value=httpx.Response(200, json=FAKE_OSRM_RESPONSE)
    )
    client = make_client()

    response = client.get(
        "/api/mapping/directions",
        params={
            "origin": "Fort Worth, TX",
            "destination": "Sushi Creek",
            "mode": "driving",
            "origin_lat": 32.7555,
            "origin_lon": -97.3308,
            "destination_lat": 32.7767,
            "destination_lon": -96.7970,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["origin"] == "Fort Worth, TX"
    assert body["destination"] == "Sushi Creek"

    requested_path = osrm_route.calls.last.request.url.path
    assert "-97.3308,32.7555" in requested_path
    assert "-96.797,32.7767" in requested_path


@respx.mock
def test_directions_404s_when_destination_not_found():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))
    client = make_client()

    response = client.get("/api/mapping/directions", params={"origin": "Fort Worth, TX", "destination": "Nowhereville"})

    assert response.status_code == 404


@respx.mock
def test_nearby_handles_way_center_and_computes_distance():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=FAKE_OVERPASS_RESPONSE))
    client = make_client()

    response = client.get(
        "/api/mapping/nearby", params={"lat": 32.7555, "lon": -97.3308, "category": "cafe", "radius_m": 1500}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {place["name"] for place in body} == {"Test Cafe", "Big Cafe"}
    assert body[0]["distance_m"] < body[1]["distance_m"]


@respx.mock
def test_nearby_includes_contact_details_when_present():
    respx.post(OVERPASS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "lat": 32.756,
                        "lon": -97.331,
                        "tags": {
                            "name": "Test Cafe",
                            "phone": "+1 555-0100",
                            "website": "https://example.com",
                            "opening_hours": "Mo-Fr 08:00-18:00",
                        },
                    }
                ]
            },
        )
    )
    client = make_client()

    response = client.get(
        "/api/mapping/nearby", params={"lat": 32.7555, "lon": -97.3308, "category": "cafe", "radius_m": 1500}
    )

    assert response.status_code == 200
    place = response.json()[0]
    assert place["phone"] == "+1 555-0100"
    assert place["website"] == "https://example.com"
    assert place["opening_hours"] == "Mo-Fr 08:00-18:00"


@respx.mock
def test_nearby_retries_transient_overpass_failure(monkeypatch):
    # overpass-api.de is a shared public instance that queues queries under
    # load, so a 504 on an otherwise-valid query is common and should be
    # retried rather than surfaced as an error straight away.
    monkeypatch.setattr("app.integrations.overpass_client.asyncio.sleep", _no_sleep)
    route = respx.post(OVERPASS_URL).mock(
        side_effect=[httpx.Response(504), httpx.Response(200, json=FAKE_OVERPASS_RESPONSE)]
    )
    client = make_client()

    response = client.get(
        "/api/mapping/nearby", params={"lat": 32.7555, "lon": -97.3308, "category": "cafe", "radius_m": 1500}
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert route.calls.call_count == 2


@respx.mock
def test_nearby_502s_after_retries_exhausted(monkeypatch):
    monkeypatch.setattr("app.integrations.overpass_client.asyncio.sleep", _no_sleep)
    route = respx.post(OVERPASS_URL).mock(return_value=httpx.Response(504))
    client = make_client()

    response = client.get(
        "/api/mapping/nearby", params={"lat": 32.7555, "lon": -97.3308, "category": "cafe", "radius_m": 1500}
    )

    assert response.status_code == 502
    assert route.calls.call_count == 3


def test_nearby_rejects_unknown_category():
    client = make_client()

    response = client.get("/api/mapping/nearby", params={"lat": 32.7555, "lon": -97.3308, "category": "spaceport"})

    assert response.status_code == 400


@respx.mock
def test_search_is_cached_between_calls():
    cache.delete("mapping:geocode:fort worth")
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_SEARCH_RESPONSE))
    client = make_client()

    client.get("/api/mapping/search", params={"q": "Fort Worth"})
    client.get("/api/mapping/search", params={"q": "Fort Worth"})

    assert route.calls.call_count == 1
