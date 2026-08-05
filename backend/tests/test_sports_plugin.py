from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx

from app.plugins.sports.plugin import SportsPlugin
from app.storage.cache import cache


def _iso_today(hour: int = 18) -> str:
    return datetime.now(UTC).replace(hour=hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%MZ")


def _iso_tomorrow(hour: int = 18) -> str:
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    return tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%MZ")


NFL_SCOREBOARD = {
    "events": [
        {
            "id": "10",
            "date": "2026-09-14T00:20Z",
            "competitions": [
                {
                    "date": "2026-09-14T00:20Z",
                    "venue": {"fullName": "MetLife Stadium"},
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "New York Giants", "abbreviation": "NYG"}},
                        {"homeAway": "away", "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"}},
                    ],
                    "broadcasts": [{"market": "national", "names": ["NBC"]}],
                    "status": {"type": {"state": "pre", "completed": False, "shortDetail": "9/13 - 8:20 PM EDT"}},
                }
            ],
        },
        {
            "id": "11",
            "date": "2026-09-14T17:00Z",
            "competitions": [
                {
                    "date": "2026-09-14T17:00Z",
                    "venue": {"fullName": "Lambeau Field"},
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Green Bay Packers", "abbreviation": "GB"}},
                        {"homeAway": "away", "team": {"displayName": "Chicago Bears", "abbreviation": "CHI"}},
                    ],
                    "broadcasts": [{"market": "away", "names": ["FOX"]}],
                    "status": {"type": {"state": "pre", "completed": False, "shortDetail": "9/14 - 1:00 PM EDT"}},
                }
            ],
        },
    ]
}

CFB_SCOREBOARD_RANKED = {
    "events": [
        {
            "id": "20",
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
                            "curatedRank": {"current": 7},
                        },
                    ],
                    "broadcasts": [{"market": "national", "names": ["ABC"]}],
                    "status": {"type": {"state": "pre", "completed": False, "shortDetail": "9/14 - 12:00 PM EDT"}},
                }
            ],
        }
    ]
}

NFL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
CFB_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

DAL_SCHEDULE = {
    "team": {"displayName": "Dallas Cowboys"},
    "events": [
        {
            "id": "1",
            "date": "2026-09-14T00:20Z",
            "competitions": [
                {
                    "date": "2026-09-14T00:20Z",
                    "venue": {"fullName": "MetLife Stadium"},
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "New York Giants", "abbreviation": "NYG"}},
                        {"homeAway": "away", "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"}},
                    ],
                    "broadcasts": [{"market": "national", "names": ["NBC"]}],
                    "status": {
                        "type": {
                            "state": "pre",
                            "completed": False,
                            "shortDetail": "9/13 - 8:20 PM EDT",
                        }
                    },
                }
            ],
        },
        {
            "id": "2",
            "date": "2026-01-04T18:00Z",
            "competitions": [
                {
                    "date": "2026-01-04T18:00Z",
                    "venue": {"fullName": "AT&T Stadium"},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"},
                            "score": {"displayValue": "24"},
                        },
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Washington Commanders", "abbreviation": "WSH"},
                            "score": {"displayValue": "17"},
                        },
                    ],
                    "broadcasts": [{"market": "national", "names": ["FOX"]}],
                    "status": {"type": {"state": "post", "completed": True, "shortDetail": "Final"}},
                }
            ],
        },
    ],
}

LAL_SCHEDULE = {
    "team": {"displayName": "Los Angeles Lakers"},
    "events": [
        {
            "id": "3",
            "date": "2026-10-20T02:00Z",
            "competitions": [
                {
                    "date": "2026-10-20T02:00Z",
                    "venue": {"fullName": "Crypto.com Arena"},
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Los Angeles Lakers", "abbreviation": "LAL"}},
                        {"homeAway": "away", "team": {"displayName": "Golden State Warriors", "abbreviation": "GSW"}},
                    ],
                    "broadcasts": [{"media": {"shortName": "ESPN"}}],
                    "status": {"type": {"state": "pre", "completed": False, "shortDetail": "10/19 - 10:00 PM EDT"}},
                }
            ],
        }
    ],
}

DAL_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule"
LAL_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/lal/schedule"


def make_plugin(**settings) -> SportsPlugin:
    # Trending is off by default in these tests (opt in per test) so that
    # followed-team tests, which don't set up scoreboard mocks or a DB for
    # `effective_settings()`, stay hermetic and network-free.
    settings.setdefault("trending_leagues", [])
    return SportsPlugin({"id": "sports", "settings": {**SportsPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin(teams=[])

    summary = await plugin.get_summary()

    assert summary == {"configured": False, "games": [], "trending": []}


async def test_get_detail_when_not_configured():
    plugin = make_plugin(teams=[])

    detail = await plugin.get_detail()

    assert detail == {"configured": False, "teams": [], "trending": [], "trending_leagues": []}


@respx.mock
async def test_get_summary_returns_next_upcoming_game_per_team():
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=DAL_SCHEDULE))
    respx.get(LAL_URL).mock(return_value=httpx.Response(200, json=LAL_SCHEDULE))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}, {"league": "nba", "team": "LAL"}])

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert "errors" not in summary
    # Only the upcoming (non-completed) game should surface, and games sort
    # chronologically across teams/leagues.
    assert [g["team"] for g in summary["games"]] == ["Dallas Cowboys", "Los Angeles Lakers"]
    dal_game = summary["games"][0]
    assert dal_game["league"] == "nfl"
    assert dal_game["league_label"] == "NFL"
    assert dal_game["opponent"] == "New York Giants"
    assert dal_game["is_home"] is False
    assert dal_game["broadcasts"] == ["NBC"]
    assert dal_game["broadcast_links"] == [{"name": "NBC", "url": "https://www.nbc.com/live"}]
    assert dal_game["state"] == "pre"


@respx.mock
async def test_get_summary_broadcast_link_is_none_for_unknown_network():
    cache._store.clear()
    unknown_network_schedule = {
        "team": {"displayName": "Dallas Cowboys"},
        "events": [
            {
                "id": "5",
                "date": "2026-09-14T00:20Z",
                "competitions": [
                    {
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
                        "broadcasts": [{"market": "regional", "names": ["KTVT"]}],
                        "status": {"type": {"state": "pre", "completed": False, "shortDetail": "9/13"}},
                    }
                ],
            }
        ],
    }
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=unknown_network_schedule))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert summary["games"][0]["broadcast_links"] == [{"name": "KTVT", "url": None}]


@respx.mock
async def test_get_summary_excludes_completed_games():
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=DAL_SCHEDULE))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert len(summary["games"]) == 1
    assert summary["games"][0]["id"] == "1"


@respx.mock
async def test_get_summary_surfaces_per_team_error_without_raising():
    cache._store.clear()
    respx.get(DAL_URL).mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["games"] == []
    assert summary["errors"] == [{"league": "nfl", "team": "DAL", "error": "Could not reach ESPN: refused"}]


async def test_get_summary_surfaces_unsupported_league_without_raising():
    cache._store.clear()
    plugin = make_plugin(teams=[{"league": "xfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["games"] == []
    assert summary["errors"][0]["error"] == "Unsupported league 'xfl'."


async def test_get_summary_surfaces_missing_team_without_raising():
    cache._store.clear()
    plugin = make_plugin(teams=[{"league": "nfl", "team": ""}])

    summary = await plugin.get_summary()

    assert summary["errors"][0]["error"] == "No team configured."


@respx.mock
async def test_get_detail_includes_multiple_upcoming_games_per_team():
    cache._store.clear()
    schedule_with_two_upcoming = {
        "team": {"displayName": "Dallas Cowboys"},
        "events": DAL_SCHEDULE["events"]
        + [
            {
                "id": "4",
                "date": "2026-09-21T17:00Z",
                "competitions": [
                    {
                        "date": "2026-09-21T17:00Z",
                        "venue": {"fullName": "AT&T Stadium"},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"}},
                            {"homeAway": "away", "team": {"displayName": "Chicago Bears", "abbreviation": "CHI"}},
                        ],
                        "broadcasts": [{"market": "national", "names": ["CBS"]}],
                        "status": {"type": {"state": "pre", "completed": False, "shortDetail": "9/21"}},
                    }
                ],
            }
        ],
    }
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=schedule_with_two_upcoming))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    detail = await plugin.get_detail()

    assert detail["configured"] is True
    assert len(detail["teams"]) == 1
    team = detail["teams"][0]
    assert team["team_name"] == "Dallas Cowboys"
    assert team["league_label"] == "NFL"
    assert len(team["games"]) == 2
    assert team["games"][0]["opponent"] == "New York Giants"
    assert team["games"][1]["opponent"] == "Chicago Bears"
    assert team["games"][1]["is_home"] is True


@respx.mock
async def test_get_detail_surfaces_error_per_team_without_raising():
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    detail = await plugin.get_detail()

    assert detail["teams"][0]["games"] == []
    assert "error" in detail["teams"][0]


@respx.mock
async def test_responses_are_cached_between_calls():
    cache._store.clear()
    route = respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=DAL_SCHEDULE))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    await plugin.get_summary()
    await plugin.get_summary()

    assert route.call_count == 1


async def test_get_ai_tools_returns_upcoming_trending_and_todays_games_tools(tmp_db):
    cache._store.clear()
    plugin = make_plugin(teams=[])

    tools = plugin.get_ai_tools()

    assert [t.name for t in tools] == [
        "get_upcoming_games_sports",
        "get_trending_games_sports",
        "get_todays_games_sports",
    ]
    result = await tools[0].handler()
    assert result == {"configured": False, "games": [], "trending": []}
    trending_result = await tools[1].handler()
    assert trending_result == {"games": []}
    todays_result = await tools[2].handler()
    assert todays_result == {"games": []}


@respx.mock
async def test_get_todays_games_includes_followed_team_game_happening_today(tmp_db):
    cache._store.clear()
    schedule = {
        "team": {"displayName": "Dallas Cowboys"},
        "events": [
            {
                "id": "100",
                "date": _iso_today(),
                "competitions": [
                    {
                        "date": _iso_today(),
                        "venue": {"fullName": "AT&T Stadium"},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"}},
                            {"homeAway": "away", "team": {"displayName": "New York Giants", "abbreviation": "NYG"}},
                        ],
                        "broadcasts": [{"market": "national", "names": ["FOX"]}],
                        "status": {"type": {"state": "pre", "completed": False, "shortDetail": "today"}},
                    }
                ],
            },
            {
                "id": "101",
                "date": _iso_tomorrow(),
                "competitions": [
                    {
                        "date": _iso_tomorrow(),
                        "venue": {"fullName": "AT&T Stadium"},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"}},
                            {"homeAway": "away", "team": {"displayName": "Chicago Bears", "abbreviation": "CHI"}},
                        ],
                        "broadcasts": [{"market": "national", "names": ["CBS"]}],
                        "status": {"type": {"state": "pre", "completed": False, "shortDetail": "tomorrow"}},
                    }
                ],
            },
        ],
    }
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=schedule))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    result = await plugin._fetch_todays_games()

    assert [g["id"] for g in result["games"]] == ["100"]
    assert result["games"][0]["broadcast_links"] == [{"name": "FOX", "url": "https://www.fox.com/live"}]


@respx.mock
async def test_get_todays_games_excludes_games_not_happening_today(tmp_db):
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=DAL_SCHEDULE))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    result = await plugin._fetch_todays_games()

    # DAL_SCHEDULE's only upcoming game is dated 2026-09-14, not "today".
    assert result["games"] == []


@respx.mock
async def test_get_todays_games_merges_trending_and_dedupes_by_id(tmp_db):
    cache._store.clear()
    respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    # Same game id as NFL_SCOREBOARD's first event, but dated "today" (real
    # time) so it passes the followed-team side's today-filter — this is
    # what should get deduped against trending's copy of the same game.
    dal_game_today = {
        **NFL_SCOREBOARD["events"][0],
        "date": _iso_today(),
        "competitions": [{**NFL_SCOREBOARD["events"][0]["competitions"][0], "date": _iso_today()}],
    }
    dal_schedule = {"team": {"displayName": "Dallas Cowboys"}, "events": [dal_game_today]}
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=dal_schedule))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}], trending_leagues=["nfl"])

    result = await plugin._fetch_todays_games()

    # Game "10" is a followed (DAL) game that also shows up in trending — it
    # should appear once, and game "11" (trending-only) should still show.
    assert sorted(g["id"] for g in result["games"]) == ["10", "11"]


@respx.mock
async def test_trending_is_populated_even_without_followed_teams(tmp_db):
    cache._store.clear()
    respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    respx.get(CFB_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=CFB_SCOREBOARD_RANKED))
    plugin = make_plugin(teams=[], trending_leagues=["nfl", "college-football"])

    summary = await plugin.get_summary()

    assert summary["configured"] is False
    assert summary["games"] == []
    assert len(summary["trending"]) > 0


@respx.mock
async def test_trending_ranks_ranked_teams_then_national_broadcasts_then_others(tmp_db):
    cache._store.clear()
    respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    respx.get(CFB_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=CFB_SCOREBOARD_RANKED))
    plugin = make_plugin(teams=[], trending_leagues=["nfl", "college-football"])

    detail = await plugin.get_detail()

    assert [g["id"] for g in detail["trending"]] == ["20", "10", "11"]
    ranked_game = detail["trending"][0]
    assert ranked_game["home_rank"] == 3
    assert ranked_game["away_rank"] == 7
    assert ranked_game["league"] == "college-football"
    assert ranked_game["league_label"] == "College Football"
    assert ranked_game["broadcast_links"] == [{"name": "ABC", "url": "https://abc.com/watch-live"}]
    assert detail["trending_leagues"] == ["nfl", "college-football"]


@respx.mock
async def test_trending_surfaces_per_league_error_without_raising(tmp_db):
    cache._store.clear()
    respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    respx.get(CFB_SCOREBOARD_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin(teams=[], trending_leagues=["nfl", "college-football"])

    summary = await plugin.get_summary()

    assert [g["id"] for g in summary["trending"]] == ["10", "11"]
    assert summary["trending_errors"] == [{"league": "college-football", "error": "ESPN request failed (HTTP 500)."}]


async def test_trending_surfaces_unsupported_league_without_raising(tmp_db):
    cache._store.clear()
    plugin = make_plugin(teams=[], trending_leagues=["xfl"])

    summary = await plugin.get_summary()

    assert summary["trending"] == []
    assert summary["trending_errors"] == [{"league": "xfl", "error": "Unsupported league 'xfl'."}]


@respx.mock
async def test_trending_responses_are_cached_between_calls(tmp_db):
    cache._store.clear()
    route = respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    plugin = make_plugin(teams=[], trending_leagues=["nfl"])

    await plugin.get_summary()
    await plugin.get_summary()

    assert route.call_count == 1
