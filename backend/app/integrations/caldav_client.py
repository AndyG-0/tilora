"""Generic CalDAV client for the calendar plugin's non-Google provider.

Covers iCloud, Fastmail, Nextcloud, and most self-hosted calendars via a
server URL + username + app-password — no OAuth app registration needed,
unlike the Google Calendar provider (see `google_oauth.py`). The `caldav`
library is sync, so calls are wrapped in `asyncio.to_thread` to keep this
matching the plugin's async interface.
"""

from __future__ import annotations

import asyncio
import zlib
from datetime import UTC, datetime, timedelta
from typing import Any

import caldav

# caldav.DAVClient defaults to no timeout at all — pin one so a hung/slow
# CalDAV server can't tie up a thread-pool worker indefinitely (this runs
# via asyncio.to_thread, matching every other sync integration client here).
_TIMEOUT_SECONDS = 10

# Fixed categorical palette (CVD-safe in this order — do not reorder) used to
# assign each calendar a distinct default color with no setup required. Users
# can override any of these from the widget's "Manage calendars" picker.
_DEFAULT_PALETTE = [
    "#2a78d6",  # blue
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
    "#e87ba4",  # magenta
    "#eb6834",  # orange
]


def default_color_for(calendar_id: str) -> str:
    return _DEFAULT_PALETTE[zlib.crc32(calendar_id.encode()) % len(_DEFAULT_PALETTE)]


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("caldav_url") and settings.get("caldav_username") and settings.get("caldav_password"))


def _resolve_calendars(client: caldav.DAVClient, calendar_ids: list[str] | None) -> list[caldav.Calendar]:
    calendars = client.principal().calendars()
    if not calendars:
        return []
    if not calendar_ids:
        # No selection made yet — default to the account's first calendar,
        # same as the original single-calendar behavior.
        return [calendars[0]]
    wanted = set(calendar_ids)
    return [calendar for calendar in calendars if calendar.id in wanted]


def _calendar_dict(calendar: caldav.Calendar) -> dict[str, Any]:
    return {"id": calendar.id, "name": calendar.name or calendar.id, "color": default_color_for(calendar.id)}


def _list_calendars_sync(url: str, username: str, password: str) -> list[dict[str, Any]]:
    client = caldav.DAVClient(url=url, username=username, password=password, timeout=_TIMEOUT_SECONDS)
    calendars = client.principal().calendars()
    return sorted((_calendar_dict(calendar) for calendar in calendars), key=lambda c: c["name"])


async def list_calendars(url: str, username: str, password: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_calendars_sync, url, username, password)


def _event_dict(event: caldav.Event, calendar_id: str, calendar_name: str) -> dict[str, Any]:
    component = event.icalendar_component
    dtstart = component["dtstart"].dt
    all_day = not isinstance(dtstart, datetime)
    return {
        "id": str(component.get("uid", event.id)),
        "title": str(component.get("summary", "(untitled)")),
        "start": dtstart.isoformat() if all_day else dtstart.astimezone(UTC).isoformat(),
        "all_day": all_day,
        "location": str(component["location"]) if component.get("location") else None,
        "calendar": calendar_name,
        "calendar_id": calendar_id,
        "color": default_color_for(calendar_id),
    }


def _fetch_events_sync(
    url: str, username: str, password: str, calendar_ids: list[str] | None, days_ahead: int
) -> list[dict[str, Any]]:
    client = caldav.DAVClient(url=url, username=username, password=password, timeout=_TIMEOUT_SECONDS)
    calendars = _resolve_calendars(client, calendar_ids)
    if not calendars:
        return []

    now = datetime.now(UTC)
    events = [
        _event_dict(event, calendar.id, calendar.name or calendar.id)
        for calendar in calendars
        for event in calendar.search(start=now, end=now + timedelta(days=days_ahead), event=True, expand=True)
    ]
    return sorted(events, key=lambda e: e["start"])


async def fetch_events(
    url: str, username: str, password: str, calendar_ids: list[str] | None, days_ahead: int
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_events_sync, url, username, password, calendar_ids, days_ahead)
