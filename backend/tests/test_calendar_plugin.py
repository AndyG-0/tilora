from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx

from app.config import settings as app_settings
from app.plugins.calendar import plugin as calendar_plugin_module
from app.plugins.calendar.plugin import CaldavCalendarPlugin, CalendarPlugin, MicrosoftCalendarPlugin
from app.storage import db

EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
MICROSOFT_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/calendarView"

EVENTS_RESPONSE = {
    "items": [
        {
            "id": "e1",
            "summary": "Team sync",
            "start": {"dateTime": "2026-01-01T10:00:00Z"},
            "location": "Room 1",
        },
        {
            "id": "e2",
            "summary": "Holiday",
            "start": {"date": "2026-01-02"},
        },
    ]
}

MICROSOFT_EVENTS_RESPONSE = {
    "value": [
        {
            "id": "e1",
            "subject": "Team sync",
            "isAllDay": False,
            "start": {"dateTime": "2026-01-01T10:00:00.0000000", "timeZone": "UTC"},
            "end": {"dateTime": "2026-01-01T10:30:00.0000000", "timeZone": "UTC"},
            "location": {"displayName": "Room 1"},
        },
        {
            "id": "e2",
            "subject": "Holiday",
            "isAllDay": True,
            "start": {"dateTime": "2026-01-02T00:00:00.0000000", "timeZone": "UTC"},
            "end": {"dateTime": "2026-01-03T00:00:00.0000000", "timeZone": "UTC"},
            "location": {"displayName": ""},
        },
    ]
}


def make_plugin(**settings) -> CalendarPlugin:
    return CalendarPlugin({"id": "calendar", "settings": settings})


async def test_get_summary_when_not_connected(tmp_db):
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {"connected": False, "provider": "google", "events": []}


@respx.mock
async def test_get_summary_maps_events_when_connected(tmp_db):
    db.save_oauth_tokens(
        "google_calendar", refresh_token="r1", access_token="a1", expires_at="2099-01-01T00:00:00+00:00"
    )
    respx.get(EVENTS_URL).mock(return_value=httpx.Response(200, json=EVENTS_RESPONSE))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["events"] == [
        {
            "id": "e1",
            "title": "Team sync",
            "start": "2026-01-01T10:00:00Z",
            "all_day": False,
            "location": "Room 1",
        },
        {
            "id": "e2",
            "title": "Holiday",
            "start": "2026-01-02",
            "all_day": True,
            "location": None,
        },
    ]


@respx.mock
async def test_get_detail_uses_calendar_id_setting(tmp_db):
    db.save_oauth_tokens(
        "google_calendar", refresh_token="r1", access_token="a1", expires_at="2099-01-01T00:00:00+00:00"
    )
    route = respx.get("https://www.googleapis.com/calendar/v3/calendars/work%40example.com/events").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    plugin = make_plugin(calendar_id="work@example.com")

    await plugin.get_detail()

    assert route.called


@respx.mock
async def test_get_ai_tools_exposes_upcoming_and_todays_events_tools(tmp_db):
    db.save_oauth_tokens(
        "google_calendar", refresh_token="r1", access_token="a1", expires_at="2099-01-01T00:00:00+00:00"
    )
    respx.get(EVENTS_URL).mock(return_value=httpx.Response(200, json=EVENTS_RESPONSE))
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert [t.name for t in tools] == ["get_upcoming_events_calendar", "get_todays_events_calendar"]
    result = await tools[0].handler()
    assert result["connected"] is True
    assert result["events"][0]["title"] == "Team sync"


@respx.mock
async def test_get_todays_events_filters_to_events_happening_today(tmp_db):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    events_response = {
        "items": [
            {"id": "t1", "summary": "Standup", "start": {"dateTime": f"{today}T10:00:00Z"}},
            {"id": "t2", "summary": "Holiday", "start": {"date": today}},
            {"id": "t3", "summary": "Later", "start": {"dateTime": f"{tomorrow}T10:00:00Z"}},
        ]
    }
    db.save_oauth_tokens(
        "google_calendar", refresh_token="r1", access_token="a1", expires_at="2099-01-01T00:00:00+00:00"
    )
    respx.get(EVENTS_URL).mock(return_value=httpx.Response(200, json=events_response))
    plugin = make_plugin()

    tools = plugin.get_ai_tools()
    result = await tools[1].handler()

    assert result["connected"] is True
    assert sorted(e["id"] for e in result["events"]) == ["t1", "t2"]


async def test_get_summary_caldav_not_configured(tmp_db):
    plugin = make_plugin(provider="caldav")

    summary = await plugin.get_summary()

    assert summary == {"connected": False, "provider": "caldav", "events": []}


async def test_get_summary_caldav_configured(tmp_db, monkeypatch):
    monkeypatch.setattr(app_settings, "caldav_url", "https://caldav.example.com")
    monkeypatch.setattr(app_settings, "caldav_username", "user")
    monkeypatch.setattr(app_settings, "caldav_password", "pass")

    async def fake_fetch_events(url, username, password, calendar_ids, days_ahead):
        assert url == "https://caldav.example.com"
        assert username == "user"
        assert password == "pass"
        assert calendar_ids == ["home-id"]
        assert days_ahead == 7
        return [
            {
                "id": "e1",
                "title": "Standup",
                "start": "2026-01-01T10:00:00+00:00",
                "all_day": False,
                "location": None,
                "calendar": "Home",
                "calendar_id": "home-id",
                "color": "#2a78d6",
            }
        ]

    monkeypatch.setattr(calendar_plugin_module.caldav_client, "fetch_events", fake_fetch_events)
    plugin = make_plugin(provider="caldav", calendar_ids=["home-id"])

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["events"][0]["title"] == "Standup"
    assert summary["events"][0]["color"] == "#2a78d6"


async def test_get_detail_caldav_includes_calendar_ids(tmp_db, monkeypatch):
    monkeypatch.setattr(app_settings, "caldav_url", "https://caldav.example.com")
    monkeypatch.setattr(app_settings, "caldav_username", "user")
    monkeypatch.setattr(app_settings, "caldav_password", "pass")

    async def fake_fetch_events(url, username, password, calendar_ids, days_ahead):
        return []

    monkeypatch.setattr(calendar_plugin_module.caldav_client, "fetch_events", fake_fetch_events)
    plugin = make_plugin(provider="caldav", calendar_ids=["home-id", "work-id"])

    detail = await plugin.get_detail()

    assert detail["calendar_ids"] == ["home-id", "work-id"]


async def test_get_summary_caldav_calendar_colors_override_default(tmp_db, monkeypatch):
    monkeypatch.setattr(app_settings, "caldav_url", "https://caldav.example.com")
    monkeypatch.setattr(app_settings, "caldav_username", "user")
    monkeypatch.setattr(app_settings, "caldav_password", "pass")

    async def fake_fetch_events(url, username, password, calendar_ids, days_ahead):
        return [
            {
                "id": "e1",
                "title": "Standup",
                "start": "2026-01-01T10:00:00+00:00",
                "all_day": False,
                "location": None,
                "calendar": "Home",
                "calendar_id": "home-id",
                "color": "#2a78d6",
            },
            {
                "id": "e2",
                "title": "Review",
                "start": "2026-01-02T10:00:00+00:00",
                "all_day": False,
                "location": None,
                "calendar": "Work",
                "calendar_id": "work-id",
                "color": "#1baf7a",
            },
        ]

    monkeypatch.setattr(calendar_plugin_module.caldav_client, "fetch_events", fake_fetch_events)
    plugin = make_plugin(
        provider="caldav",
        calendar_ids=["home-id", "work-id"],
        calendar_colors={"home-id": "#ff0000"},
    )

    summary = await plugin.get_summary()

    colors_by_id = {e["calendar_id"]: e["color"] for e in summary["events"]}
    assert colors_by_id == {"home-id": "#ff0000", "work-id": "#1baf7a"}


def test_caldav_calendar_plugin_defaults_to_caldav_provider(tmp_db):
    plugin = CaldavCalendarPlugin({"id": "calendar_caldav", "settings": dict(CaldavCalendarPlugin.default_settings)})

    assert plugin.provider == "caldav"


async def test_get_summary_microsoft_when_not_connected(tmp_db):
    plugin = make_plugin(provider="microsoft")

    summary = await plugin.get_summary()

    assert summary == {"connected": False, "provider": "microsoft", "events": []}


@respx.mock
async def test_get_summary_microsoft_maps_events_when_connected(tmp_db):
    db.save_oauth_tokens(
        "microsoft_calendar", refresh_token="r1", access_token="a1", expires_at="2099-01-01T00:00:00+00:00"
    )
    respx.get(MICROSOFT_EVENTS_URL).mock(return_value=httpx.Response(200, json=MICROSOFT_EVENTS_RESPONSE))
    plugin = make_plugin(provider="microsoft")

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["events"] == [
        {
            "id": "e1",
            "title": "Team sync",
            "start": "2026-01-01T10:00:00.0000000Z",
            "all_day": False,
            "location": "Room 1",
        },
        {
            "id": "e2",
            "title": "Holiday",
            "start": "2026-01-02",
            "all_day": True,
            "location": None,
        },
    ]


def test_microsoft_calendar_plugin_defaults_to_microsoft_provider(tmp_db):
    plugin = MicrosoftCalendarPlugin(
        {"id": "calendar_microsoft", "settings": dict(MicrosoftCalendarPlugin.default_settings)}
    )

    assert plugin.provider == "microsoft"
