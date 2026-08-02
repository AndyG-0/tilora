from __future__ import annotations

import httpx
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import sports

TEAMS_RESPONSE = {
    "sports": [{"leagues": [{"teams": [{"team": {"abbreviation": "DAL", "displayName": "Dallas Cowboys"}}]}]}]
}


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(sports.router)
    return TestClient(app)


@respx.mock
def test_list_teams_returns_teams_for_league():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams").mock(
        return_value=httpx.Response(200, json=TEAMS_RESPONSE)
    )
    client = make_client()

    response = client.get("/api/sports/nfl/teams")

    assert response.status_code == 200
    assert response.json() == [{"abbreviation": "DAL", "display_name": "Dallas Cowboys"}]


def test_list_teams_rejects_unsupported_league():
    client = make_client()

    response = client.get("/api/sports/xfl/teams")

    assert response.status_code == 400


@respx.mock
def test_list_teams_returns_502_on_espn_failure():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams").mock(return_value=httpx.Response(500))
    client = make_client()

    response = client.get("/api/sports/nfl/teams")

    assert response.status_code == 502
