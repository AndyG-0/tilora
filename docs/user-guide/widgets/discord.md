# Discord Widget

The **Discord** widget (`type: discord`) connects a designated Discord text channel or thread to stream live messages and announcements directly onto your dashboard.

---

## Features

- **Multiple Display Modes**:
    - `static`: Scrollable list of recent messages.
    - `marquee`: Continuous scrolling horizontal ticker.
    - `fade`: Cycles through individual messages one at a time with smooth crossfades.
- **Customizable Time Windows & Limits**: Drop messages older than $N$ minutes or limit to recent items.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: discord
  type: discord
  enabled: true
  layout: { col: 4, row: 5, colSpan: 1, rowSpan: 1 }
  settings:
    channel_id: "123456789012345678"
    message_limit: 20
    time_window_minutes: null # e.g. 1440 for 24 hours
    display_mode: static # "static", "marquee", or "fade"
    marquee_speed_seconds: 40
    fade_interval_seconds: 6
```

---

## Setup Requirements

1. Create a Discord bot at [discord.com/developers/applications](https://discord.com/developers/applications).
2. Enter the bot token in **Settings → Admin settings → Discord**.
3. Invite the bot to your Discord server with Read Messages and Read Message History permissions.
