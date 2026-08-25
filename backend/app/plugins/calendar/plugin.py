"""Calendar plugin: upcoming events from Google Calendar, Microsoft 365 /
Outlook Calendar, or a generic CalDAV server (iCloud, Fastmail, Nextcloud,
most self-hosted calendars).

`settings.provider` picks which ("google", the default, "microsoft", or
"caldav"). Google and Microsoft both require the user to connect their
account from the Settings page (see app/api/calendar_auth.py); CalDAV
requires the caldav_url/username/password app settings (see
app/integrations/caldav_client.py). Until connected/configured,
get_summary/get_detail return an empty, not-connected state rather than
raising, so the widget degrades gracefully.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from app.config import effective_settings, resolve_timezone
from app.i18n import t
from app.integrations import caldav_client, google_oauth, microsoft_oauth
from app.plugins.base import Plugin, ToolDef

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_MICROSOFT_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/calendarView"
_SUMMARY_EVENT_COUNT = 5


def _event_is_today(event: dict[str, Any], tz: ZoneInfo) -> bool:
    start = event.get("start")
    if not start:
        return False
    today = datetime.now(tz).strftime("%Y-%m-%d")
    if event.get("all_day"):
        return start[:10] == today
    try:
        event_start = datetime.fromisoformat(start)
    except ValueError:
        return False
    return event_start.astimezone(tz).strftime("%Y-%m-%d") == today


class CalendarPlugin(Plugin):
    id = "calendar"
    name = "Google Calendar"
    refresh_interval_seconds = 300
    # Which calendars/colors/days-ahead to show is a personal preference, not
    # a shared household setting — see Plugin.settings_scope. The OAuth
    # client credentials and CalDAV/iCloud account credentials this plugin
    # reads via effective_settings() stay app-level/admin-only; only the
    # per-widget selection below becomes per-user.
    settings_scope = "personal"
    default_settings = {
        "provider": "google",
        "calendar_id": "primary",
        "days_ahead": 7,
        "calendar_colors": {},
    }

    @property
    def provider(self) -> str:
        return self.config["settings"].get("provider", "google")

    @property
    def calendar_id(self) -> str:
        return self.config["settings"].get("calendar_id", "primary")

    @property
    def calendar_ids(self) -> list[str]:
        return self.config["settings"].get("calendar_ids") or []

    @property
    def calendar_colors(self) -> dict[str, str]:
        return self.config["settings"].get("calendar_colors") or {}

    @property
    def days_ahead(self) -> int:
        return int(self.config["settings"].get("days_ahead", 7))

    async def _is_connected(self) -> bool:
        if self.provider == "caldav":
            return caldav_client.is_configured(await effective_settings())
        if self.provider == "microsoft":
            return microsoft_oauth.is_connected()
        return google_oauth.is_connected()

    async def _fetch_events(self) -> list[dict[str, Any]]:
        if self.provider == "caldav":
            return await self._fetch_caldav_events()
        if self.provider == "microsoft":
            return await self._fetch_microsoft_events()
        return await self._fetch_google_events()

    async def _fetch_caldav_events(self) -> list[dict[str, Any]]:
        creds = await effective_settings()
        if not caldav_client.is_configured(creds):
            return []
        events = await caldav_client.fetch_events(
            creds["caldav_url"],
            creds["caldav_username"],
            creds["caldav_password"],
            self.calendar_ids,
            self.days_ahead,
        )
        overrides = self.calendar_colors
        for event in events:
            event["color"] = overrides.get(event["calendar_id"], event["color"])
        return events

    async def _fetch_google_events(self) -> list[dict[str, Any]]:
        access_token = await google_oauth.get_valid_access_token()
        if access_token is None:
            return []

        now = datetime.now(UTC)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                _EVENTS_URL.format(calendar_id=quote(self.calendar_id, safe="")),
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "timeMin": now.isoformat(),
                    "timeMax": (now + timedelta(days=self.days_ahead)).isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
        response.raise_for_status()

        events = []
        for item in response.json().get("items", []):
            start = item.get("start", {})
            events.append(
                {
                    "id": item["id"],
                    "title": item.get("summary") or t("calendar.event.untitled", self.locale),
                    "start": start.get("dateTime") or start.get("date"),
                    "all_day": "date" in start,
                    "location": item.get("location"),
                }
            )
        return events

    async def _fetch_microsoft_events(self) -> list[dict[str, Any]]:
        access_token = await microsoft_oauth.get_valid_access_token()
        if access_token is None:
            return []

        now = datetime.now(UTC)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                _MICROSOFT_EVENTS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    # Makes the naive dateTime strings below consistently
                    # UTC regardless of the account's mailbox timezone
                    # setting (Graph's documented default without this
                    # header is also UTC, but this makes that explicit).
                    "Prefer": 'outlook.timezone="UTC"',
                },
                params={
                    "startDateTime": now.isoformat(),
                    "endDateTime": (now + timedelta(days=self.days_ahead)).isoformat(),
                    "$orderby": "start/dateTime",
                },
            )
        response.raise_for_status()

        events = []
        for item in response.json().get("value", []):
            start = item.get("start", {})
            all_day = bool(item.get("isAllDay"))
            raw_start = start.get("dateTime")
            if all_day:
                # Graph returns an all-day event's start as a midnight
                # dateTime (e.g. "2026-01-02T00:00:00.0000000"), not a bare
                # date like Google's `start.date` — trim to just the date
                # portion so this matches Google's all-day shape.
                start_value = raw_start[:10] if raw_start else None
            else:
                # Graph's dateTime is a naive string with no "Z"/offset even
                # though the Prefer header above makes it UTC — append "Z"
                # so it parses as UTC downstream (see this module's and
                # microsoft_oauth.py's docstrings for the confirming source).
                start_value = f"{raw_start}Z" if raw_start and not raw_start.endswith("Z") else raw_start
            location = item.get("location") or {}
            events.append(
                {
                    "id": item["id"],
                    "title": item.get("subject") or t("calendar.event.untitled", self.locale),
                    "start": start_value,
                    "all_day": all_day,
                    "location": location.get("displayName") or None,
                }
            )
        return events

    async def get_summary(self) -> dict[str, Any]:
        events = await self._fetch_events()
        return {
            "connected": await self._is_connected(),
            "provider": self.provider,
            "events": events[:_SUMMARY_EVENT_COUNT],
        }

    async def get_detail(self) -> dict[str, Any]:
        events = await self._fetch_events()
        return {
            "connected": await self._is_connected(),
            "provider": self.provider,
            "events": events,
            "calendar_ids": self.calendar_ids,
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_upcoming_events() -> dict[str, Any]:
            return await self.get_summary()

        async def get_todays_events() -> dict[str, Any]:
            events = await self._fetch_events()
            tz = resolve_timezone((await effective_settings())["timezone"])
            todays_events = [event for event in events if _event_is_today(event, tz)]
            return {"connected": await self._is_connected(), "provider": self.provider, "events": todays_events}

        return [
            ToolDef(
                name=f"get_upcoming_events_{self.id}",
                description=f"Get the person's upcoming events from their {self.name}.",
                parameters={"type": "object", "properties": {}},
                handler=get_upcoming_events,
            ),
            ToolDef(
                name=f"get_todays_events_{self.id}",
                description=f"Get the person's {self.name} events happening today. Use this for requests "
                "like 'what's on my calendar today', 'read my calendar', or 'do I have anything today'.",
                parameters={"type": "object", "properties": {}},
                handler=get_todays_events,
            ),
        ]


class CaldavCalendarPlugin(CalendarPlugin):
    """Same plugin, distinct type/name so it's selectable from the "add widget" UI."""

    id = "calendar_caldav"
    name = "CalDAV Calendar"
    default_settings = {"provider": "caldav", "days_ahead": 7, "calendar_colors": {}}


class MicrosoftCalendarPlugin(CalendarPlugin):
    """Same plugin, distinct type/name so it's selectable from the "add widget" UI."""

    id = "calendar_microsoft"
    name = "Outlook Calendar"
    default_settings = {"provider": "microsoft", "calendar_id": "primary", "days_ahead": 7, "calendar_colors": {}}
