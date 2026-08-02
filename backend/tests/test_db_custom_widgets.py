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


def test_removed_widget_ids_empty_when_unset(tmp_db):
    assert db.removed_widget_ids() == set()


def test_mark_widget_removed_then_removed_widget_ids_round_trips(tmp_db):
    db.mark_widget_removed("clock")

    assert db.removed_widget_ids() == {"clock"}


def test_mark_widget_removed_is_idempotent(tmp_db):
    db.mark_widget_removed("clock")
    db.mark_widget_removed("clock")

    assert db.removed_widget_ids() == {"clock"}
