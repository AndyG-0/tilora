# Battlefield (BF6) Widget

The **BF6** widget (`type: bf6`) displays live player statistics and game server status for Battlefield titles via the community-maintained `gametools.network` API.

---

## Features

- **Live Server Tracker**: Displays current player count, map name, mode, and ping for a specified community server.
- **Player Stats**: Tracks player kills, deaths, K/D ratio, rank, score per minute, and win percentage across platforms.
- **No API Key Required**: Powered by public community endpoints.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: bf6
  type: bf6
  enabled: true
  layout: { col: 3, row: 12, colSpan: 2, rowSpan: 1 }
  settings:
    server_name: "Hardcore 24/7"
    player_name: "GamerTag"
    platform: "pc" # One of: pc, steam, ea, epic, xbox, xboxone, xboxseries, psn, ps4, ps5
```
