from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx

from app.plugins.sports.plugin import _DETAIL_GAMES_PER_TEAM, SportsPlugin
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
    # followed-team-only tests don't need scoreboard mocks. Any test that
    # configures a followed team still needs the `tmp_db` fixture, though —
    # `get_summary`/`get_detail` resolve a timezone via `effective_settings()`
    # (DB-backed) to split games into today/upcoming.
    settings.setdefault("trending_leagues", [])
    return SportsPlugin({"id": "sports", "settings": {**SportsPlugin.default_settings, **settings}})


def test_settings_scope_is_personal():
    # Favorite teams are each household member's own choice, not shared —
    # see Plugin.settings_scope.
    assert SportsPlugin.settings_scope == "personal"


async def test_get_summary_when_not_configured():
    plugin = make_plugin(teams=[])

    summary = await plugin.get_summary()

    assert summary == {"configured": False, "todays_games": [], "trending": [], "upcoming_games": []}


async def test_get_detail_when_not_configured():
    plugin = make_plugin(teams=[])

    detail = await plugin.get_detail()

    assert detail == {
        "configured": False,
        "teams": [],
        "todays_games": [],
        "trending": [],
        "upcoming_games": [],
        "trending_leagues": [],
    }


@respx.mock
async def test_get_summary_returns_next_upcoming_game_per_team(tmp_db):
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=DAL_SCHEDULE))
    respx.get(LAL_URL).mock(return_value=httpx.Response(200, json=LAL_SCHEDULE))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}, {"league": "nba", "team": "LAL"}])

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert "errors" not in summary
    # Only the upcoming (non-completed) game should surface, and games sort
    # chronologically across teams/leagues. Neither team's game is dated
    # "today", so both land in upcoming_games.
    assert summary["todays_games"] == []
    assert [g["team"] for g in summary["upcoming_games"]] == ["Dallas Cowboys", "Los Angeles Lakers"]
    dal_game = summary["upcoming_games"][0]
    assert dal_game["league"] == "nfl"
    assert dal_game["league_label"] == "NFL"
    assert dal_game["opponent"] == "New York Giants"
    assert dal_game["is_home"] is False
    assert dal_game["broadcasts"] == ["NBC"]
    assert dal_game["broadcast_links"] == [{"name": "NBC", "url": "https://www.nbc.com/live"}]
    assert dal_game["state"] == "pre"
    assert dal_game["team_espn_url"] == "https://www.espn.com/nfl/team/_/name/dal"


@respx.mock
async def test_get_summary_broadcast_link_is_none_for_unknown_network(tmp_db):
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

    assert summary["upcoming_games"][0]["broadcast_links"] == [{"name": "KTVT", "url": None}]


@respx.mock
async def test_get_summary_excludes_completed_games(tmp_db):
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=DAL_SCHEDULE))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert len(summary["upcoming_games"]) == 1
    assert summary["upcoming_games"][0]["id"] == "1"


@respx.mock
async def test_get_summary_surfaces_per_team_error_without_raising(tmp_db):
    cache._store.clear()
    respx.get(DAL_URL).mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["todays_games"] == []
    assert summary["upcoming_games"] == []
    assert summary["errors"] == [{"league": "nfl", "team": "DAL", "error": "Could not reach ESPN: refused"}]


async def test_get_summary_surfaces_unsupported_league_without_raising(tmp_db):
    cache._store.clear()
    plugin = make_plugin(teams=[{"league": "xfl", "team": "DAL"}])

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["todays_games"] == []
    assert summary["upcoming_games"] == []
    assert summary["errors"][0]["error"] == "Unsupported league 'xfl'."


async def test_get_summary_surfaces_missing_team_without_raising(tmp_db):
    cache._store.clear()
    plugin = make_plugin(teams=[{"league": "nfl", "team": ""}])

    summary = await plugin.get_summary()

    assert summary["errors"][0]["error"] == "No team configured."


@respx.mock
async def test_get_detail_includes_multiple_upcoming_games_per_team(tmp_db):
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
    assert "games" not in team
    assert detail["todays_games"] == []
    assert len(detail["upcoming_games"]) == 2
    assert detail["upcoming_games"][0]["opponent"] == "New York Giants"
    assert detail["upcoming_games"][1]["opponent"] == "Chicago Bears"
    assert detail["upcoming_games"][1]["is_home"] is True


@respx.mock
async def test_get_detail_surfaces_error_per_team_without_raising(tmp_db):
    cache._store.clear()
    respx.get(DAL_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    detail = await plugin.get_detail()

    assert "error" in detail["teams"][0]
    assert detail["todays_games"] == []
    assert detail["upcoming_games"] == []


@respx.mock
async def test_get_summary_splits_todays_and_upcoming_games(tmp_db):
    cache._store.clear()
    schedule = {
        "team": {"displayName": "Dallas Cowboys"},
        "events": [
            {
                "id": "200",
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
                "id": "201",
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

    summary = await plugin.get_summary()

    assert [g["id"] for g in summary["todays_games"]] == ["200"]
    assert [g["id"] for g in summary["upcoming_games"]] == ["201"]


@respx.mock
async def test_get_summary_dedupes_trending_against_todays_games(tmp_db):
    cache._store.clear()
    respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    # Same game id as NFL_SCOREBOARD's first event, but dated "today" (real
    # time) so it also passes the followed-team side's today-filter.
    dal_game_today = {
        **NFL_SCOREBOARD["events"][0],
        "date": _iso_today(),
        "competitions": [{**NFL_SCOREBOARD["events"][0]["competitions"][0], "date": _iso_today()}],
    }
    dal_schedule = {"team": {"displayName": "Dallas Cowboys"}, "events": [dal_game_today]}
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=dal_schedule))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}], trending_leagues=["nfl"])

    summary = await plugin.get_summary()

    # Game "10" is a followed (DAL) game today that also shows up in
    # trending — it should surface only in todays_games, not trending.
    assert [g["id"] for g in summary["todays_games"]] == ["10"]
    assert [g["id"] for g in summary["trending"]] == ["11"]


@respx.mock
async def test_get_detail_splits_todays_and_upcoming_games(tmp_db):
    cache._store.clear()
    schedule = {
        "team": {"displayName": "Dallas Cowboys"},
        "events": [
            {
                "id": "200",
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
                "id": "201",
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

    detail = await plugin.get_detail()

    assert "games" not in detail["teams"][0]
    assert [g["id"] for g in detail["todays_games"]] == ["200"]
    assert [g["id"] for g in detail["upcoming_games"]] == ["201"]


@respx.mock
async def test_get_detail_dedupes_trending_against_todays_games(tmp_db):
    cache._store.clear()
    respx.get(NFL_SCOREBOARD_URL).mock(return_value=httpx.Response(200, json=NFL_SCOREBOARD))
    dal_game_today = {
        **NFL_SCOREBOARD["events"][0],
        "date": _iso_today(),
        "competitions": [{**NFL_SCOREBOARD["events"][0]["competitions"][0], "date": _iso_today()}],
    }
    dal_schedule = {"team": {"displayName": "Dallas Cowboys"}, "events": [dal_game_today]}
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=dal_schedule))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}], trending_leagues=["nfl"])

    detail = await plugin.get_detail()

    assert [g["id"] for g in detail["todays_games"]] == ["10"]
    assert [g["id"] for g in detail["trending"]] == ["11"]


@respx.mock
async def test_get_detail_upcoming_games_respects_per_team_limit_but_today_is_uncapped(tmp_db):
    cache._store.clear()
    future_events = [
        {
            "id": f"3{i}",
            "date": _iso_tomorrow(hour=i),
            "competitions": [
                {
                    "date": _iso_tomorrow(hour=i),
                    "venue": {"fullName": "AT&T Stadium"},
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Dallas Cowboys", "abbreviation": "DAL"}},
                        {"homeAway": "away", "team": {"displayName": f"Opponent {i}", "abbreviation": f"OP{i}"}},
                    ],
                    "broadcasts": [],
                    "status": {"type": {"state": "pre", "completed": False, "shortDetail": "tomorrow"}},
                }
            ],
        }
        for i in range(1, 8)
    ]
    schedule = {"team": {"displayName": "Dallas Cowboys"}, "events": future_events}
    respx.get(DAL_URL).mock(return_value=httpx.Response(200, json=schedule))
    plugin = make_plugin(teams=[{"league": "nfl", "team": "DAL"}])

    detail = await plugin.get_detail()

    assert len(future_events) > _DETAIL_GAMES_PER_TEAM
    assert len(detail["upcoming_games"]) == _DETAIL_GAMES_PER_TEAM


@respx.mock
async def test_responses_are_cached_between_calls(tmp_db):
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
    assert result == {"configured": False, "todays_games": [], "trending": [], "upcoming_games": []}
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
    assert summary["todays_games"] == []
    assert summary["upcoming_games"] == []
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
    assert ranked_game["home_espn_url"] == "https://www.espn.com/college-football/team/_/name/osu"
    assert ranked_game["away_espn_url"] == "https://www.espn.com/college-football/team/_/name/tex"
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
