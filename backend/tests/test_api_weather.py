from __future__ import annotations

import httpx
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import weather
from app.api.weather import GEOCODING_URL

FAKE_RESPONSE = {
    "results": [
        {
            "name": "Fort Worth",
            "admin1": "Texas",
            "country": "United States",
            "latitude": 32.7555,
            "longitude": -97.3308,
        },
        {
            "name": "Fort Worth",
            "admin1": "Kansas",
            "country": "United States",
            "latitude": 39.0,
            "longitude": -95.0,
        },
    ]
}


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(weather.router)
    return TestClient(app)


@respx.mock
def test_search_cities_maps_geocoding_results():
    respx.get(GEOCODING_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    client = make_client()

    response = client.get("/api/weather/search", params={"q": "Fort Worth"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Fort Worth",
            "admin1": "Texas",
            "country": "United States",
            "latitude": 32.7555,
            "longitude": -97.3308,
        },
        {
            "name": "Fort Worth",
            "admin1": "Kansas",
            "country": "United States",
            "latitude": 39.0,
            "longitude": -95.0,
        },
    ]


@respx.mock
def test_search_cities_returns_empty_list_when_no_matches():
    respx.get(GEOCODING_URL).mock(return_value=httpx.Response(200, json={}))
    client = make_client()

    response = client.get("/api/weather/search", params={"q": "asdfghjkl"})

    assert response.status_code == 200
    assert response.json() == []


def test_search_cities_requires_query_param():
    client = make_client()

    response = client.get("/api/weather/search")

    assert response.status_code == 422
