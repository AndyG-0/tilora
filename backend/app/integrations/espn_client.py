"""ESPN "site API" client for the sports schedule plugin.

Targets ESPN's free, unauthenticated public JSON endpoints (the same ones
the espn.com website itself calls, and widely used by hobbyist projects —
there's no official key-based API, and no key is needed):

    https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{team}/schedule

`{sport}/{league}` is a fixed pair per league (see `LEAGUE_PATHS`), and
`{team}` is ESPN's team abbreviation (e.g. "DAL"), accepted case-insensitively
in the URL. This per-team schedule endpoint is used rather than the
league-wide `.../scoreboard` endpoint (which only covers a single day/week
and would require matching team names client-side) — the schedule endpoint
returns a whole season for one team directly, already sorted chronologically,
and includes the same per-competition `status`/`broadcasts` data.

No auth, no retries/backoff beyond what's standard elsewhere in this
codebase (see docker_client.py) — a single request, wrapped in an
integration-specific error.
"""

from __future__ import annotations

from typing import Any

import httpx

# sport/league path segments for each supported league, keyed by the id used
# in this plugin's settings (`{"league": "nfl", "team": "DAL"}`, etc.).
LEAGUE_PATHS: dict[str, str] = {
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "college-football": "football/college-football",
    "wnba": "basketball/wnba",
    "college-basketball-men": "basketball/mens-college-basketball",
    "college-basketball-women": "basketball/womens-college-basketball",
}

LEAGUE_LABELS: dict[str, str] = {
    "nfl": "NFL",
    "nba": "NBA",
    "mlb": "MLB",
    "nhl": "NHL",
    "college-football": "College Football",
    "wnba": "WNBA",
    "college-basketball-men": "College Basketball (Men)",
    "college-basketball-women": "College Basketball (Women)",
}

_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"


class ESPNError(Exception):
    """Raised when ESPN's site API can't be reached or returns something unusable."""


def is_supported_league(league: str) -> bool:
    return league in LEAGUE_PATHS


def supported_leagues() -> list[str]:
    return list(LEAGUE_PATHS)


async def fetch_team_schedule(league: str, team: str) -> dict[str, Any]:
    """Fetch a single team's full-season schedule.

    `team` is ESPN's team abbreviation (e.g. "DAL", "LAL") — case-insensitive.
    Raises `ESPNError` (never lets httpx/JSON errors escape) on any failure:
    unsupported league, network error, non-2xx response, non-JSON body, or a
    JSON body that doesn't look like a schedule response.
    """
    sport_league = LEAGUE_PATHS.get(league)
    if sport_league is None:
        raise ESPNError(f"Unsupported league '{league}'.")
    if not team:
        raise ESPNError("No team specified.")

    url = f"{_BASE_URL}/{sport_league}/teams/{team.lower()}/schedule"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            raise ESPNError(f"Could not reach ESPN: {exc}") from exc

    if response.status_code == 404:
        raise ESPNError(f"Unknown team '{team}' in {LEAGUE_LABELS.get(league, league)}.")
    if response.status_code >= 400:
        raise ESPNError(f"ESPN request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise ESPNError(f"Unexpected (non-JSON) response from ESPN: {exc}") from exc

    if not isinstance(data, dict) or "events" not in data:
        raise ESPNError("Unexpected response shape from ESPN.")

    return data


async def fetch_teams(league: str) -> list[dict[str, str]]:
    """Fetch every team in a league, for populating a team picker.

    Returns `[{"abbreviation": ..., "display_name": ...}, ...]`, sorted by
    display name. Raises `ESPNError` on any failure, same contract as
    `fetch_team_schedule`.
    """
    sport_league = LEAGUE_PATHS.get(league)
    if sport_league is None:
        raise ESPNError(f"Unsupported league '{league}'.")

    url = f"{_BASE_URL}/{sport_league}/teams"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url, params={"limit": 200})
        except httpx.HTTPError as exc:
            raise ESPNError(f"Could not reach ESPN: {exc}") from exc

    if response.status_code >= 400:
        raise ESPNError(f"ESPN request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise ESPNError(f"Unexpected (non-JSON) response from ESPN: {exc}") from exc

    try:
        leagues = data["sports"][0]["leagues"]
        entries = leagues[0]["teams"] if leagues else []
    except (KeyError, IndexError, TypeError) as exc:
        raise ESPNError("Unexpected response shape from ESPN.") from exc

    teams: list[dict[str, str]] = []
    for entry in entries:
        team = entry.get("team") if isinstance(entry, dict) else None
        if not isinstance(team, dict):
            continue
        abbreviation = team.get("abbreviation")
        display_name = team.get("displayName")
        if abbreviation and display_name:
            teams.append({"abbreviation": abbreviation, "display_name": display_name})

    teams.sort(key=lambda t: t["display_name"])
    return teams


async def fetch_scoreboard(league: str, date: str) -> dict[str, Any]:
    """Fetch a league's full slate of games for a single day.

    `date` is `YYYYMMDD` (ESPN's `dates` query param) — passed explicitly
    rather than omitted, since ESPN's no-param default falls back to the
    *next* scheduled slate (confirmed live: querying an off-season/off-day
    league returns games weeks away) rather than an empty list, which would
    be misleading for a "what's on today" view.

    Raises `ESPNError` (never lets httpx/JSON errors escape) on any
    failure, same contract as `fetch_team_schedule`.
    """
    sport_league = LEAGUE_PATHS.get(league)
    if sport_league is None:
        raise ESPNError(f"Unsupported league '{league}'.")

    url = f"{_BASE_URL}/{sport_league}/scoreboard"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url, params={"dates": date})
        except httpx.HTTPError as exc:
            raise ESPNError(f"Could not reach ESPN: {exc}") from exc

    if response.status_code >= 400:
        raise ESPNError(f"ESPN request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise ESPNError(f"Unexpected (non-JSON) response from ESPN: {exc}") from exc

    if not isinstance(data, dict) or "events" not in data:
        raise ESPNError("Unexpected response shape from ESPN.")

    return data


def _broadcast_names(competition: dict[str, Any]) -> list[str]:
    # ESPN uses two different broadcast shapes across its endpoints (and
    # sometimes within the same one): the scoreboard endpoint's
    # {"market": ..., "names": [...]} and the team-schedule endpoint's
    # {"type": ..., "media": {"shortName": ...}}. Handle both, deduped.
    names: list[str] = []
    for broadcast in competition.get("broadcasts") or []:
        if not isinstance(broadcast, dict):
            continue
        for name in broadcast.get("names") or []:
            if name and name not in names:
                names.append(name)
        media = broadcast.get("media")
        if isinstance(media, dict):
            short_name = media.get("shortName")
            if short_name and short_name not in names:
                names.append(short_name)
    return names


def _score(competitor: dict[str, Any]) -> str | None:
    score = competitor.get("score")
    if isinstance(score, dict):
        return score.get("displayValue")
    if isinstance(score, str) and score:
        return score
    return None


def parse_team_schedule(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Normalize a `fetch_team_schedule` response into (team display name, games).

    Each game dict has: id, date (ISO 8601 string), state ("pre"/"in"/"post"),
    completed (bool), status_detail (short human string, e.g. "Final" or
    "8/6 - 8:00 PM EDT"), home/away team names + abbreviations + scores,
    broadcasts (list of network/streaming service names), and venue.
    Events with a malformed/incomplete shape are skipped rather than raising.
    """
    team_info = data.get("team")
    team_name = team_info.get("displayName") if isinstance(team_info, dict) else None

    games: list[dict[str, Any]] = []
    for event in data.get("events") or []:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], dict):
            continue
        competition = competitions[0]

        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "away"), None)
        if home is None or away is None:
            continue

        status = competition.get("status") or event.get("status") or {}
        status_type = status.get("type") or {} if isinstance(status, dict) else {}

        home_team = home.get("team") or {}
        away_team = away.get("team") or {}
        venue = competition.get("venue") or {}

        games.append(
            {
                "id": event.get("id", ""),
                "date": event.get("date") or competition.get("date"),
                "state": status_type.get("state", "pre"),
                "completed": bool(status_type.get("completed", False)),
                "status_detail": status_type.get("shortDetail") or status_type.get("detail") or "",
                "home_team": home_team.get("displayName", ""),
                "home_abbreviation": home_team.get("abbreviation", ""),
                "away_team": away_team.get("displayName", ""),
                "away_abbreviation": away_team.get("abbreviation", ""),
                "home_score": _score(home),
                "away_score": _score(away),
                "broadcasts": _broadcast_names(competition),
                "venue": venue.get("fullName"),
            }
        )

    return team_name or "", games


def _broadcasts_with_market(competition: dict[str, Any]) -> list[dict[str, str]]:
    # Same two broadcast shapes as `_broadcast_names`, but keeps the
    # "national" vs. local-market distinction — used to weight nationally
    # televised games higher when ranking trending games.
    broadcasts: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for broadcast in competition.get("broadcasts") or []:
        if not isinstance(broadcast, dict):
            continue
        market = broadcast.get("market")
        market = market if isinstance(market, str) else ""
        for name in broadcast.get("names") or []:
            if name and name not in seen_names:
                seen_names.add(name)
                broadcasts.append({"name": name, "market": market})
        media = broadcast.get("media")
        if isinstance(media, dict):
            short_name = media.get("shortName")
            if short_name and short_name not in seen_names:
                seen_names.add(short_name)
                broadcasts.append({"name": short_name, "market": market})
    return broadcasts


def _rank(competitor: dict[str, Any]) -> int | None:
    rank = competitor.get("curatedRank")
    if not isinstance(rank, dict):
        return None
    current = rank.get("current")
    if isinstance(current, int) and 1 <= current <= 25:
        return current
    return None


def parse_scoreboard(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize a `fetch_scoreboard` response into a flat list of games.

    Unlike `parse_team_schedule`, this has no "my team's" perspective —
    it's a league-wide slate for one day. Each game dict has: id, date,
    state, completed, status_detail, home/away team names + abbreviations +
    ranks (Top-25 `curatedRank`, `None` if unranked) + scores, broadcasts
    (list of `{"name": ..., "market": ...}`), and venue. Events with a
    malformed/incomplete shape are skipped rather than raising.
    """
    games: list[dict[str, Any]] = []
    for event in data.get("events") or []:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], dict):
            continue
        competition = competitions[0]

        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "away"), None)
        if home is None or away is None:
            continue

        status = competition.get("status") or event.get("status") or {}
        status_type = status.get("type") or {} if isinstance(status, dict) else {}

        home_team = home.get("team") or {}
        away_team = away.get("team") or {}
        venue = competition.get("venue") or {}

        games.append(
            {
                "id": event.get("id", ""),
                "date": event.get("date") or competition.get("date"),
                "state": status_type.get("state", "pre"),
                "completed": bool(status_type.get("completed", False)),
                "status_detail": status_type.get("shortDetail") or status_type.get("detail") or "",
                "home_team": home_team.get("displayName", ""),
                "home_abbreviation": home_team.get("abbreviation", ""),
                "home_rank": _rank(home),
                "away_team": away_team.get("displayName", ""),
                "away_abbreviation": away_team.get("abbreviation", ""),
                "away_rank": _rank(away),
                "home_score": _score(home),
                "away_score": _score(away),
                "broadcasts": _broadcasts_with_market(competition),
                "venue": venue.get("fullName"),
            }
        )

    return games
