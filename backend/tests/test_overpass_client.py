from __future__ import annotations

import re
from urllib.parse import parse_qs

import httpx
import respx

from app.integrations import overpass_client
from app.integrations.overpass_client import BASE_URL

FAKE_RESPONSE = {
    "elements": [
        {"type": "node", "lat": 32.760, "lon": -97.335, "tags": {"name": "Taco Bell"}},
        {"type": "node", "lat": 32.756, "lon": -97.331, "tags": {"name": "Taco Bell #2"}},
    ]
}


@respx.mock
async def test_find_by_name_sorts_by_distance():
    respx.post(BASE_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))

    places = await overpass_client.find_by_name(32.7555, -97.3308, "Taco Bell")

    assert [p["name"] for p in places] == ["Taco Bell #2", "Taco Bell"]
    assert places[0]["distance_m"] < places[1]["distance_m"]


@respx.mock
async def test_find_by_name_escapes_regex_special_characters():
    route = respx.post(BASE_URL).mock(return_value=httpx.Response(200, json={"elements": []}))

    await overpass_client.find_by_name(32.7555, -97.3308, "Sushi (Downtown)")

    body = route.calls.last.request.content.decode()
    sent_query = parse_qs(body)["data"][0]
    assert re.escape("Sushi (Downtown)") in sent_query


@respx.mock
async def test_find_by_name_returns_empty_list_when_no_matches():
    respx.post(BASE_URL).mock(return_value=httpx.Response(200, json={"elements": []}))

    places = await overpass_client.find_by_name(32.7555, -97.3308, "Nowhere Cafe")

    assert places == []


@respx.mock
async def test_find_by_name_respects_limit():
    respx.post(BASE_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))

    places = await overpass_client.find_by_name(32.7555, -97.3308, "Taco Bell", limit=1)

    assert len(places) == 1
    assert places[0]["name"] == "Taco Bell #2"
