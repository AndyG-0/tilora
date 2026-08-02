"""Team lookup for the sports schedule widget's settings UI.

Separate from `widgets.py`'s generic summary/detail/settings routes since
this isn't per-widget: it's a league-wide team list backing the "pick a
team" dropdown on the sports widget's detail page. ESPN's team roster per
league barely changes (only on relocation/rebrand), so it's cached far
longer than the 15-minute schedule cache in `app/plugins/sports/plugin.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.integrations import espn_client
from app.storage.cache import cache

_CACHE_TTL_SECONDS = 86400  # 24 hours — team rosters are near-static

router = APIRouter(prefix="/api/sports", tags=["sports"])


@router.get("/{league}/teams")
async def list_teams(league: str):
    if not espn_client.is_supported_league(league):
        raise HTTPException(status_code=400, detail=f"Unsupported league '{league}'")

    cache_key = f"sports_teams:{league}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        teams = await espn_client.fetch_teams(league)
    except espn_client.ESPNError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cache.set(cache_key, teams, _CACHE_TTL_SECONDS)
    return teams
