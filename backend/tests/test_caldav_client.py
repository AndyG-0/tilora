from __future__ import annotations

from datetime import UTC, date, datetime

from icalendar import Event as ICalEvent

from app.integrations import caldav_client


class FakeEvent:
    def __init__(self, component, event_id):
        self.icalendar_component = component
        self.id = event_id


class FakeCalendar:
    def __init__(self, name, id=None, events=None):
        self.name = name
        self.id = id or name
        self._events = events or []

    def search(self, **kwargs):
        return self._events


class FakePrincipal:
    def __init__(self, calendars):
        self._calendars = calendars

    def calendars(self):
        return self._calendars


class FakeClient:
    def __init__(self, calendars):
        self._calendars = calendars

    def principal(self):
        return FakePrincipal(self._calendars)


def _component(uid, summary, dtstart, location=None):
    comp = ICalEvent()
    comp.add("uid", uid)
    comp.add("summary", summary)
    comp.add("dtstart", dtstart)
    if location is not None:
        comp.add("location", location)
    return comp


def test_is_configured_true_when_all_set():
    assert caldav_client.is_configured({"caldav_url": "https://x", "caldav_username": "u", "caldav_password": "p"})


def test_is_configured_false_when_any_missing():
    assert not caldav_client.is_configured({"caldav_url": "https://x", "caldav_username": "u"})


def test_event_dict_maps_timed_event():
    component = _component("e1", "Team sync", datetime(2026, 1, 1, 10, 0, tzinfo=UTC), location="Room 1")
    event = FakeEvent(component, "e1")

    result = caldav_client._event_dict(event, "home-id", "Home")

    assert result == {
        "id": "e1",
        "title": "Team sync",
        "start": "2026-01-01T10:00:00+00:00",
        "all_day": False,
        "location": "Room 1",
        "calendar": "Home",
        "calendar_id": "home-id",
        "color": caldav_client.default_color_for("home-id"),
    }


def test_event_dict_maps_all_day_event():
    component = _component("e2", "Holiday", date(2026, 1, 2))
    event = FakeEvent(component, "e2")

    result = caldav_client._event_dict(event, "home-id", "Home")

    assert result["all_day"] is True
    assert result["location"] is None
    assert result["start"] == "2026-01-02"


def test_calendar_dict_falls_back_to_id_when_name_missing():
    calendar = FakeCalendar(name=None, id="cal-1")

    assert caldav_client._calendar_dict(calendar) == {
        "id": "cal-1",
        "name": "cal-1",
        "color": caldav_client.default_color_for("cal-1"),
    }


def test_list_calendars_sync_sorted_by_name(monkeypatch):
    work = FakeCalendar("Work", id="work-id")
    home = FakeCalendar("Home", id="home-id")
    monkeypatch.setattr(caldav_client.caldav, "DAVClient", lambda **kwargs: FakeClient([work, home]))

    calendars = caldav_client._list_calendars_sync("https://x", "user", "pass")

    assert calendars == [
        {"id": "home-id", "name": "Home", "color": caldav_client.default_color_for("home-id")},
        {"id": "work-id", "name": "Work", "color": caldav_client.default_color_for("work-id")},
    ]


def test_default_color_for_is_deterministic():
    assert caldav_client.default_color_for("home-id") == caldav_client.default_color_for("home-id")


def test_default_color_for_varies_by_calendar():
    assert caldav_client.default_color_for("home-id") != caldav_client.default_color_for("work-id")


def test_resolve_calendars_matches_by_ids():
    home = FakeCalendar("Home", id="home-id")
    work = FakeCalendar("Work", id="work-id")
    client = FakeClient([home, work])

    assert caldav_client._resolve_calendars(client, ["work-id"]) == [work]
    assert caldav_client._resolve_calendars(client, ["home-id", "work-id"]) == [home, work]


def test_resolve_calendars_falls_back_to_first_when_no_ids():
    home = FakeCalendar("Home", id="home-id")
    work = FakeCalendar("Work", id="work-id")
    client = FakeClient([home, work])

    assert caldav_client._resolve_calendars(client, None) == [home]


def test_resolve_calendars_drops_stale_ids():
    home = FakeCalendar("Home", id="home-id")
    client = FakeClient([home])

    assert caldav_client._resolve_calendars(client, ["deleted-id"]) == []


def test_resolve_calendars_returns_empty_when_no_calendars():
    assert caldav_client._resolve_calendars(FakeClient([]), None) == []


def test_fetch_events_sync_merges_and_sorts_across_calendars(monkeypatch):
    later = FakeEvent(_component("e2", "Later", datetime(2026, 1, 2, 9, 0, tzinfo=UTC)), "e2")
    earlier = FakeEvent(_component("e1", "Earlier", datetime(2026, 1, 1, 9, 0, tzinfo=UTC)), "e1")
    home = FakeCalendar("Home", id="home-id", events=[later])
    work = FakeCalendar("Work", id="work-id", events=[earlier])
    monkeypatch.setattr(caldav_client.caldav, "DAVClient", lambda **kwargs: FakeClient([home, work]))

    events = caldav_client._fetch_events_sync("https://x", "user", "pass", ["home-id", "work-id"], 7)

    assert [(e["title"], e["calendar"]) for e in events] == [("Earlier", "Work"), ("Later", "Home")]
