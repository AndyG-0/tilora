# Calendar Widget

The **Calendar** widget (`type: calendar`, `calendar_caldav`, `calendar_microsoft`) connects your personal or household schedule from **Google Calendar**, **Microsoft 365 / Outlook**, or **CalDAV** (Apple iCloud, Fastmail, Nextcloud, and self-hosted servers).

---

## Features

- **Multi-Provider Support**: Connect Google Calendar OAuth, Microsoft Entra ID OAuth, or standard CalDAV.
- **Multi-Calendar Selection**: Choose one or more sub-calendars (e.g. Work, Family, Birthdays) to display together.
- **Custom Color Mapping**: Assign distinct colors to each calendar for quick visual distinction.
- **AI Tool Integration**: Exposes the `get_calendar_events` tool to the voice assistant and daily briefing.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: calendar
  type: calendar
  enabled: true
  layout: { col: 1, row: 9, colSpan: 2, rowSpan: 1 }
  settings:
    provider: google # "google", "caldav", or "microsoft"
    days_ahead: 7
```

---

## Connecting Your Account

1. Set up your OAuth credentials or CalDAV URL in **Settings → Admin settings** (see the [Calendar OAuth Guide](../../admin-guide/calendar-oauth.md)).
2. Tap the **Calendar** tile on your dashboard to open the detail view.
3. Tap **Connect account** to authenticate with your provider.
4. Tap **Manage calendars** to choose which sub-calendars to display and customize their colors.
