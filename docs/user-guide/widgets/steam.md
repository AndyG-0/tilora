# Steam Gaming Widget

The **Steam** widget (`type: steam`) connects to the Steam Web API to display your current gaming status, recent game playtime, and online friends.

---

## Features

- **Live In-Game Status**: Shows the game you are currently playing with title art and playtime.
- **Recent Playtime**: Displays games played over the past 2 weeks with total hours logged.
- **Friends List**: Lists online friends and what games they are currently playing.
- **Personal Scope**: Each household member can connect their own Steam account.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: steam
  type: steam
  enabled: true
  layout: { col: 1, row: 12, colSpan: 2, rowSpan: 1 }
  settings:
    steamid: "76561198000000000" # Your 64-bit Steam ID
    api_key: "" # Steam Web API Key
```

---

## Requirements

1. Obtain a free Steam Web API key at [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).
2. Enter your `steamid` and `api_key` in the widget settings.
3. Ensure your Steam profile's **Game Details** and **Friends List** privacy settings are set to **Public** on Steam.
