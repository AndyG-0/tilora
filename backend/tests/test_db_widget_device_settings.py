from __future__ import annotations

from app.storage import db


def test_get_widget_device_settings_returns_none_when_unset(tmp_db):
    assert db.get_widget_device_settings("device-a", "jellyfin") is None


def test_save_then_get_widget_device_settings_round_trips(tmp_db):
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible_video"})

    assert db.get_widget_device_settings("device-a", "jellyfin") == {"playback_mode": "compatible_video"}


def test_save_widget_device_settings_overwrites_prior_value_for_same_device_and_widget(tmp_db):
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible"})
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "direct"})

    assert db.get_widget_device_settings("device-a", "jellyfin") == {"playback_mode": "direct"}


def test_widget_device_settings_are_independent_per_device_for_the_same_widget(tmp_db):
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible"})
    db.save_widget_device_settings("device-b", "jellyfin", {"playback_mode": "direct"})

    assert db.get_widget_device_settings("device-a", "jellyfin") == {"playback_mode": "compatible"}
    assert db.get_widget_device_settings("device-b", "jellyfin") == {"playback_mode": "direct"}


def test_widget_device_settings_are_independent_per_widget_for_the_same_device(tmp_db):
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible"})
    db.save_widget_device_settings("device-a", "other-widget", {"some_key": "value"})

    assert db.get_widget_device_settings("device-a", "jellyfin") == {"playback_mode": "compatible"}
    assert db.get_widget_device_settings("device-a", "other-widget") == {"some_key": "value"}


def test_delete_widget_device_settings_removes_only_that_device_and_widget(tmp_db):
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible"})
    db.save_widget_device_settings("device-b", "jellyfin", {"playback_mode": "direct"})

    db.delete_widget_device_settings("device-a", "jellyfin")

    assert db.get_widget_device_settings("device-a", "jellyfin") is None
    assert db.get_widget_device_settings("device-b", "jellyfin") == {"playback_mode": "direct"}


def test_delete_widget_device_settings_for_widget_removes_every_devices_row(tmp_db):
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible"})
    db.save_widget_device_settings("device-b", "jellyfin", {"playback_mode": "direct"})
    db.save_widget_device_settings("device-a", "other-widget", {"some_key": "value"})

    db.delete_widget_device_settings_for_widget("jellyfin")

    assert db.get_widget_device_settings("device-a", "jellyfin") is None
    assert db.get_widget_device_settings("device-b", "jellyfin") is None
    # Unrelated widget for the same device is untouched.
    assert db.get_widget_device_settings("device-a", "other-widget") == {"some_key": "value"}


def test_delete_device_cascades_to_widget_device_settings(tmp_db):
    db.create_device("device-a", "Alice's iPhone", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    db.save_widget_device_settings("device-a", "jellyfin", {"playback_mode": "compatible_video"})

    db.delete_device("device-a")

    assert db.get_widget_device_settings("device-a", "jellyfin") is None
