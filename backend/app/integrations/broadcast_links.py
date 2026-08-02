"""Static broadcast-name -> watch-page URL lookup for the sports plugin.

There's no free/public "where is this game streaming" API for live sports
(TMDB's `/watch/providers`, used by the movies plugin, only covers
movies/TV). ESPN's schedule endpoint already tells us the broadcast/network
name (see `espn_client._broadcast_names`) — this just maps well-known names
to that network/service's own watch-live page, so the UI can turn "ESPN" or
"Peacock" into a clickable link. Unrecognized names (regional sports
networks, local affiliates, etc.) simply get no link.
"""

from __future__ import annotations

_LINKS: dict[str, str] = {
    "espn": "https://www.espn.com/watch",
    "espn2": "https://www.espn.com/watch",
    "espn+": "https://plus.espn.com",
    "espnu": "https://www.espn.com/watch",
    "espnews": "https://www.espn.com/watch",
    "abc": "https://abc.com/watch-live",
    "fox": "https://www.fox.com/live",
    "fs1": "https://www.foxsports.com/live",
    "fs2": "https://www.foxsports.com/live",
    "nbc": "https://www.nbc.com/live",
    "peacock": "https://www.peacocktv.com",
    "cbs": "https://www.cbs.com/live-tv",
    "paramount+": "https://www.paramountplus.com",
    "tnt": "https://www.tntdrama.com/watch-tnt",
    "tbs": "https://www.tbs.com/watch-tbs",
    "trutv": "https://www.trutv.com/watch-live",
    "prime video": "https://www.amazon.com/gp/video/storefront",
    "apple tv+": "https://tv.apple.com",
    "mlb network": "https://www.mlb.com/network",
    "nfl network": "https://www.nfl.com/network",
    "nba tv": "https://www.nba.com/watch/nba-tv",
    "nhl network": "https://www.nhl.com/video/nhl-network",
}


def link_for(broadcast_name: str) -> str | None:
    return _LINKS.get(broadcast_name.strip().lower())
