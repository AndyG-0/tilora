from __future__ import annotations

from app.storage import db

_DEFAULTS = {
    "enabled": False,
    "idle_timeout_seconds": 300,
    "rotation_interval_seconds": 25,
    "widget_ids": [],
    "text_animation_style": "marquee",
    "led_color": "#ff8a00",
    "text_pause_seconds": 8,
    "flipboard_pattern": "top_to_bottom",
}


def test_get_screensaver_settings_returns_defaults_when_unset(tmp_db):
    assert db.get_screensaver_settings("alice", "tablet") == _DEFAULTS


def test_save_then_get_screensaver_settings_round_trips(tmp_db):
    db.save_screensaver_settings(
        "alice", "tablet", {"enabled": True, "idle_timeout_seconds": 60, "widget_ids": ["clock"]}
    )

    assert db.get_screensaver_settings("alice", "tablet") == {
        "enabled": True,
        "idle_timeout_seconds": 60,
        "rotation_interval_seconds": 25,
        "widget_ids": ["clock"],
        "text_animation_style": "marquee",
        "led_color": "#ff8a00",
        "text_pause_seconds": 8,
        "flipboard_pattern": "top_to_bottom",
    }


def test_save_screensaver_settings_merges_partial_updates(tmp_db):
    db.save_screensaver_settings("alice", "tablet", {"enabled": True, "widget_ids": ["clock", "discord"]})

    db.save_screensaver_settings("alice", "tablet", {"idle_timeout_seconds": 120})

    assert db.get_screensaver_settings("alice", "tablet") == {
        "enabled": True,
        "idle_timeout_seconds": 120,
        "rotation_interval_seconds": 25,
        "widget_ids": ["clock", "discord"],
        "text_animation_style": "marquee",
        "led_color": "#ff8a00",
        "text_pause_seconds": 8,
        "flipboard_pattern": "top_to_bottom",
    }


def test_save_screensaver_settings_round_trips_flipboard_pattern(tmp_db):
    db.save_screensaver_settings("alice", "tablet", {"flipboard_pattern": "random"})

    assert db.get_screensaver_settings("alice", "tablet")["flipboard_pattern"] == "random"


def test_screensaver_settings_are_independent_per_device_for_same_user(tmp_db):
    db.save_screensaver_settings("alice", "phone", {"enabled": True})
    db.save_screensaver_settings("alice", "tablet", {"enabled": False})

    assert db.get_screensaver_settings("alice", "phone")["enabled"] is True
    assert db.get_screensaver_settings("alice", "tablet")["enabled"] is False


def test_screensaver_settings_are_independent_per_user_for_same_device(tmp_db):
    db.save_screensaver_settings("alice", "tablet", {"idle_timeout_seconds": 60})
    db.save_screensaver_settings("bob", "tablet", {"idle_timeout_seconds": 600})

    assert db.get_screensaver_settings("alice", "tablet")["idle_timeout_seconds"] == 60
    assert db.get_screensaver_settings("bob", "tablet")["idle_timeout_seconds"] == 600


def test_delete_user_removes_their_screensaver_settings(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.save_screensaver_settings("alice", "tablet", {"enabled": True})

    db.delete_user("alice")

    assert db.get_screensaver_settings("alice", "tablet") == _DEFAULTS


def test_delete_device_removes_its_screensaver_settings(tmp_db):
    db.create_device("tablet", "Tablet", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    db.save_screensaver_settings("alice", "tablet", {"enabled": True})

    db.delete_device("tablet")

    assert db.get_screensaver_settings("alice", "tablet") == _DEFAULTS
