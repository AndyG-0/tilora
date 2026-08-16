from __future__ import annotations

import httpx
import respx

from app.integrations import geocode
from app.integrations.nominatim_client import SEARCH_URL
from app.integrations.overpass_client import BASE_URL as OVERPASS_URL

FAKE_OVERPASS_RESPONSE = {"elements": [{"type": "node", "lat": 32.756, "lon": -97.331, "tags": {"name": "Taco Bell"}}]}

FAKE_NOMINATIM_RESPONSE = [
    {
        "display_name": "Taco Bell, Wichita Falls, TX",
        "name": "Taco Bell",
        "lat": "33.0",
        "lon": "-98.0",
        "class": "amenity",
        "type": "fast_food",
    }
]


async def _no_sleep(*args, **kwargs) -> None:
    return None


@respx.mock
async def test_resolve_near_prefers_overpass_match():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=FAKE_OVERPASS_RESPONSE))
    nominatim_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_NOMINATIM_RESPONSE))

    result = await geocode.resolve_near("Taco Bell", near=(32.7555, -97.3308))

    assert result == {"latitude": 32.756, "longitude": -97.331, "name": "Taco Bell"}
    assert nominatim_route.calls.call_count == 0


@respx.mock
async def test_resolve_near_falls_back_to_nominatim_when_overpass_has_no_match():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_NOMINATIM_RESPONSE))

    result = await geocode.resolve_near("Taco Bell", near=(32.7555, -97.3308))

    assert result == {"latitude": 33.0, "longitude": -98.0, "name": "Taco Bell"}


@respx.mock
async def test_resolve_near_falls_back_to_nominatim_when_overpass_errors(monkeypatch):
    monkeypatch.setattr("app.integrations.overpass_client.asyncio.sleep", _no_sleep)
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(504))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_NOMINATIM_RESPONSE))

    result = await geocode.resolve_near("Taco Bell", near=(32.7555, -97.3308))

    assert result == {"latitude": 33.0, "longitude": -98.0, "name": "Taco Bell"}


@respx.mock
async def test_resolve_near_skips_overpass_when_no_near_point():
    nominatim_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=FAKE_NOMINATIM_RESPONSE))

    result = await geocode.resolve_near("Fort Worth, TX")

    assert result == {"latitude": 33.0, "longitude": -98.0, "name": "Taco Bell"}
    assert nominatim_route.calls.call_count == 1


@respx.mock
async def test_resolve_near_returns_none_when_nothing_found():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    result = await geocode.resolve_near("Nowhereville", near=(32.7555, -97.3308))

    assert result is None
