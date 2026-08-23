# Sports Scores & Schedules Widget

The **Sports** widget (`type: sports`) tracks live scores, game times, and TV broadcast networks for your favorite teams across major sports leagues via ESPN's public endpoints.

---

## Features

- **Supported Leagues**:
    - **NFL** (National Football League)
    - **NBA** (National Basketball Association)
    - **MLB** (Major League Baseball)
    - **NHL** (National Hockey League)
    - **College Football** (NCAA FBS)
    - **WNBA** (Women's National Basketball Association)
- **Live In-Game Status**: Shows real-time scores, quarter/period, possession, and remaining clock.
- **TV Broadcast Listings**: Identifies which network or streaming channel (e.g. ESPN, FOX, CBS, NBC, Prime Video) is televising the game.
- **Top Trending Games**: Optionally track trending national matchups even for teams you don't follow.
- **Zero API Key**: Works out of the box with ESPN's public endpoints.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: sports
  type: sports
  enabled: true
  layout: { col: 3, row: 11, colSpan: 2, rowSpan: 1 }
  settings:
    teams:
      - league: nfl
        team: dal # ESPN abbreviation (Dallas Cowboys)
      - league: nba
        team: lal # Los Angeles Lakers
      - league: mlb
        team: nyy # New York Yankees
```
