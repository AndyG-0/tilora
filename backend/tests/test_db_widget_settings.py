from __future__ import annotations

from app.storage import db


def test_get_widget_settings_returns_none_when_unset(tmp_db):
    assert db.get_widget_settings("weather") is None


def test_save_then_get_widget_settings_round_trips(tmp_db):
    db.save_widget_settings("weather", {"latitude": 1.0, "longitude": 2.0})

    assert db.get_widget_settings("weather") == {"latitude": 1.0, "longitude": 2.0}


def test_save_widget_settings_overwrites_prior_value(tmp_db):
    db.save_widget_settings("weather", {"latitude": 1.0})
    db.save_widget_settings("weather", {"latitude": 5.0})

    assert db.get_widget_settings("weather") == {"latitude": 5.0}
