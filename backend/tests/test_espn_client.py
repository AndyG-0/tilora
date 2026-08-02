from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import espn_client

# Trimmed but structurally faithful copies of ESPN's real
# .../teams/{team}/schedule response shape (sampled from the live API).
SCHEDULE_RESPONSE = {
    "team": {
        "id": "6",
        "abbreviation": "DAL",
        "displayName": "Dallas Cowboys",
    },
    "events": [
        {
            "id": "401872930",
            "date": "2026-09-14T00:20Z",
            "name": "Dallas Cowboys at New York Giants",
            "competitions": [
                {
                    "id": "401872930",
                    "date": "2026-09-14T00:20Z",
                    "venue": {"fullName": "MetLife Stadium"},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"displayName": "New York Giants", "abbreviation": "NYG"},
                        },
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"},
                        },
                    ],
                    "broadcasts": [
                        {
                            "type": {"id": "1", "shortName": "TV"},
                            "market": {"id": "1", "type": "National"},
                            "media": {"shortName": "NBC"},
                        }
                    ],
                    "status": {
                        "type": {
                            "id": "1",
                            "name": "STATUS_SCHEDULED",
                            "state": "pre",
                            "completed": False,
                            "detail": "Sun, September 13th at 8:20 PM EDT",
                            "shortDetail": "9/13 - 8:20 PM EDT",
                        }
                    },
                }
            ],
        },
        {
            "id": "401872900",
            "date": "2026-01-04T18:00Z",
            "name": "Washington Commanders at Dallas Cowboys",
            "competitions": [
                {
                    "id": "401872900",
                    "date": "2026-01-04T18:00Z",
                    "venue": {"fullName": "AT&T Stadium"},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"},
                            "score": {"value": 24.0, "displayValue": "24"},
                        },
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Washington Commanders", "abbreviation": "WSH"},
                            "score": {"value": 17.0, "displayValue": "17"},
                        },
                    ],
                    "broadcasts": [{"market": "national", "names": ["FOX"]}],
                    "status": {
                        "type": {
                            "id": "3",
                            "name": "STATUS_FINAL",
                            "state": "post",
                            "completed": True,
                            "detail": "Final",
                            "shortDetail": "Final",
                        }
                    },
                }
            ],
        },
    ],
}


TEAMS_RESPONSE = {
    "sports": [
        {
            "leagues": [
                {
                    "teams": [
                        {"team": {"abbreviation": "WSH", "displayName": "Washington Commanders"}},
                        {"team": {"abbreviation": "DAL", "displayName": "Dallas Cowboys"}},
                        {"team": {"abbreviation": "", "displayName": "Missing Abbreviation"}},
                    ]
                }
            ]
        }
    ]
}


def test_is_supported_league():
    assert espn_client.is_supported_league("nfl")
    assert espn_client.is_supported_league("college-football")
    assert not espn_client.is_supported_league("xfl")


def test_supported_leagues_lists_all_known_leagues():
    leagues = espn_client.supported_leagues()
    for league in (
        "nfl",
        "nba",
        "mlb",
        "nhl",
        "college-football",
        "wnba",
        "college-basketball-men",
        "college-basketball-women",
    ):
        assert league in leagues


@respx.mock
async def test_fetch_team_schedule_builds_correct_url_lowercased():
    route = respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule").mock(
        return_value=httpx.Response(200, json=SCHEDULE_RESPONSE)
    )

    data = await espn_client.fetch_team_schedule("nfl", "DAL")

    assert route.called
    assert data == SCHEDULE_RESPONSE


async def test_fetch_team_schedule_raises_for_unsupported_league():
    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_team_schedule("xfl", "DAL")


async def test_fetch_team_schedule_raises_without_team():
    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_team_schedule("nfl", "")


@respx.mock
async def test_fetch_team_schedule_raises_on_connect_error():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule").mock(
        side_effect=httpx.ConnectError("refused")
    )

    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_team_schedule("nfl", "DAL")


@respx.mock
async def test_fetch_team_schedule_raises_on_404():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/zzz/schedule").mock(
        return_value=httpx.Response(404)
    )

    with pytest.raises(espn_client.ESPNError, match="Unknown team"):
        await espn_client.fetch_team_schedule("nfl", "ZZZ")


@respx.mock
async def test_fetch_team_schedule_raises_on_server_error():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_team_schedule("nfl", "DAL")


@respx.mock
async def test_fetch_team_schedule_raises_on_non_json_response():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_team_schedule("nfl", "DAL")


@respx.mock
async def test_fetch_team_schedule_raises_on_unexpected_shape():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule").mock(
        return_value=httpx.Response(200, json={"oops": True})
    )

    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_team_schedule("nfl", "DAL")


@respx.mock
async def test_fetch_teams_returns_sorted_teams_and_skips_incomplete_entries():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams").mock(
        return_value=httpx.Response(200, json=TEAMS_RESPONSE)
    )

    teams = await espn_client.fetch_teams("nfl")

    assert teams == [
        {"abbreviation": "DAL", "display_name": "Dallas Cowboys"},
        {"abbreviation": "WSH", "display_name": "Washington Commanders"},
    ]


async def test_fetch_teams_raises_for_unsupported_league():
    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_teams("xfl")


@respx.mock
async def test_fetch_teams_raises_on_unexpected_shape():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams").mock(
        return_value=httpx.Response(200, json={"oops": True})
    )

    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_teams("nfl")


def test_parse_team_schedule_extracts_team_name_and_games():
    team_name, games = espn_client.parse_team_schedule(SCHEDULE_RESPONSE)

    assert team_name == "Dallas Cowboys"
    assert len(games) == 2


def test_parse_team_schedule_normalizes_upcoming_game_fields():
    _, games = espn_client.parse_team_schedule(SCHEDULE_RESPONSE)
    upcoming = games[0]

    assert upcoming["id"] == "401872930"
    assert upcoming["date"] == "2026-09-14T00:20Z"
    assert upcoming["state"] == "pre"
    assert upcoming["completed"] is False
    assert upcoming["status_detail"] == "9/13 - 8:20 PM EDT"
    assert upcoming["home_team"] == "New York Giants"
    assert upcoming["home_abbreviation"] == "NYG"
    assert upcoming["away_team"] == "Dallas Cowboys"
    assert upcoming["away_abbreviation"] == "DAL"
    assert upcoming["home_score"] is None
    assert upcoming["away_score"] is None
    assert upcoming["broadcasts"] == ["NBC"]
    assert upcoming["venue"] == "MetLife Stadium"


def test_parse_team_schedule_normalizes_completed_game_scores_and_broadcast_names_shape():
    _, games = espn_client.parse_team_schedule(SCHEDULE_RESPONSE)
    final = games[1]

    assert final["state"] == "post"
    assert final["completed"] is True
    assert final["home_score"] == "24"
    assert final["away_score"] == "17"
    assert final["broadcasts"] == ["FOX"]


def test_parse_team_schedule_skips_malformed_events():
    data = {
        "team": {"displayName": "Dallas Cowboys"},
        "events": [
            {"id": "no-competitions"},
            {"id": "empty-competitions", "competitions": []},
            {"id": "no-competitors", "competitions": [{"competitors": []}]},
            {"id": "missing-home", "competitions": [{"competitors": [{"homeAway": "away", "team": {}}]}]},
            "not-a-dict",
        ],
    }

    _, games = espn_client.parse_team_schedule(data)

    assert games == []


def test_parse_team_schedule_handles_missing_team_info():
    team_name, games = espn_client.parse_team_schedule({"events": []})

    assert team_name == ""
    assert games == []


SCOREBOARD_RESPONSE = {
    "events": [
        {
            "id": "401872930",
            "date": "2026-09-14T16:00Z",
            "competitions": [
                {
                    "date": "2026-09-14T16:00Z",
                    "venue": {"fullName": "Ohio Stadium"},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Ohio State Buckeyes", "abbreviation": "OSU"},
                            "curatedRank": {"current": 3},
                        },
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Texas Longhorns", "abbreviation": "TEX"},
                            "curatedRank": {"current": 99},
                            "score": {"displayValue": "10"},
                        },
                    ],
                    "broadcasts": [{"market": "national", "names": ["ABC"]}],
                    "status": {
                        "type": {
                            "id": "1",
                            "state": "pre",
                            "completed": False,
                            "shortDetail": "9/14 - 12:00 PM EDT",
                        }
                    },
                }
            ],
        }
    ]
}


@respx.mock
async def test_fetch_scoreboard_builds_dates_qualified_url():
    route = respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard").mock(
        return_value=httpx.Response(200, json=SCOREBOARD_RESPONSE)
    )

    data = await espn_client.fetch_scoreboard("nfl", "20260914")

    assert route.called
    assert route.calls.last.request.url.params["dates"] == "20260914"
    assert data == SCOREBOARD_RESPONSE


async def test_fetch_scoreboard_raises_for_unsupported_league():
    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_scoreboard("xfl", "20260914")


@respx.mock
async def test_fetch_scoreboard_raises_on_server_error():
    respx.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(espn_client.ESPNError):
        await espn_client.fetch_scoreboard("nfl", "20260914")


def test_parse_scoreboard_normalizes_ranks_and_broadcast_market():
    games = espn_client.parse_scoreboard(SCOREBOARD_RESPONSE)

    assert len(games) == 1
    game = games[0]
    assert game["id"] == "401872930"
    assert game["home_team"] == "Ohio State Buckeyes"
    assert game["home_rank"] == 3
    assert game["away_team"] == "Texas Longhorns"
    # curatedRank of 99 means unranked — only 1-25 is kept.
    assert game["away_rank"] is None
    assert game["away_score"] == "10"
    assert game["broadcasts"] == [{"name": "ABC", "market": "national"}]
    assert game["venue"] == "Ohio Stadium"


def test_parse_scoreboard_skips_malformed_events():
    data = {
        "events": [
            {"id": "no-competitions"},
            {"id": "empty-competitions", "competitions": []},
            {"id": "no-competitors", "competitions": [{"competitors": []}]},
            {"id": "missing-home", "competitions": [{"competitors": [{"homeAway": "away", "team": {}}]}]},
            "not-a-dict",
        ]
    }

    games = espn_client.parse_scoreboard(data)

    assert games == []
