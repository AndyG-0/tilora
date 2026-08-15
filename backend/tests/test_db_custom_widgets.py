from __future__ import annotations

from app.storage import db


def test_list_custom_widgets_empty_when_unset(tmp_db):
    assert db.list_custom_widgets() == []


def test_save_then_list_custom_widgets_round_trips(tmp_db):
    db.save_custom_widget("weather-abc123", "weather", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, "home")

    assert db.list_custom_widgets() == [
        {
            "id": "weather-abc123",
            "type": "weather",
            "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
            "tab": "home",
            "owner_user_id": None,
            "owner_device_id": None,
        }
    ]


def test_save_custom_widget_allows_null_tab(tmp_db):
    db.save_custom_widget("weather-abc123", "weather", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, None)

    assert db.list_custom_widgets()[0]["tab"] is None


def test_save_custom_widget_overwrites_prior_value(tmp_db):
    db.save_custom_widget("weather-abc123", "weather", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, "home")
    db.save_custom_widget("weather-abc123", "weather", {"col": 2, "row": 3, "colSpan": 1, "rowSpan": 1}, "media")

    widgets = db.list_custom_widgets()
    assert len(widgets) == 1
    assert widgets[0]["layout"] == {"col": 2, "row": 3, "colSpan": 1, "rowSpan": 1}
    assert widgets[0]["tab"] == "media"


def test_delete_custom_widget_removes_it(tmp_db):
    db.save_custom_widget("weather-abc123", "weather", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, None)

    db.delete_custom_widget("weather-abc123")

    assert db.list_custom_widgets() == []


def test_delete_custom_widget_is_noop_when_absent(tmp_db):
    db.delete_custom_widget("nonexistent")

    assert db.list_custom_widgets() == []


def test_save_custom_widget_records_owner_user_and_device(tmp_db):
    db.save_custom_widget(
        "weather-abc123",
        "weather",
        {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        None,
        owner_user_id="alice",
        owner_device_id="dev1",
    )

    widget = db.list_custom_widgets()[0]
    assert widget["owner_user_id"] == "alice"
    assert widget["owner_device_id"] == "dev1"


def test_hidden_widget_ids_empty_when_unset(tmp_db):
    assert db.hidden_widget_ids("alice", "dev1") == set()


def test_hide_widget_then_hidden_widget_ids_round_trips(tmp_db):
    db.hide_widget("alice", "dev1", "clock")

    assert db.hidden_widget_ids("alice", "dev1") == {"clock"}


def test_hide_widget_is_idempotent(tmp_db):
    db.hide_widget("alice", "dev1", "clock")
    db.hide_widget("alice", "dev1", "clock")

    assert db.hidden_widget_ids("alice", "dev1") == {"clock"}


def test_hide_widget_is_independent_per_user_and_device(tmp_db):
    # Hiding a shared default tile is a per-(user, device) preference, not a
    # global delete — see app.api.widgets.remove_widget.
    db.hide_widget("alice", "dev1", "clock")

    assert db.hidden_widget_ids("alice", "dev2") == set()
    assert db.hidden_widget_ids("bob", "dev1") == set()


def test_delete_hidden_widget_ids_for_widget_clears_every_user_and_device(tmp_db):
    db.hide_widget("alice", "dev1", "clock")
    db.hide_widget("bob", "dev2", "clock")

    db.delete_hidden_widget_ids_for_widget("clock")

    assert db.hidden_widget_ids("alice", "dev1") == set()
    assert db.hidden_widget_ids("bob", "dev2") == set()
