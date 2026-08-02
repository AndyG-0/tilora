from __future__ import annotations

from app.storage import db


def test_get_app_settings_returns_empty_dict_when_unset(tmp_db):
    assert db.get_app_settings() == {}


def test_save_then_get_app_settings_round_trips(tmp_db):
    db.save_app_settings({"timezone": "America/Chicago", "ai_model": "openai/gpt-5"})

    assert db.get_app_settings() == {"timezone": "America/Chicago", "ai_model": "openai/gpt-5"}


def test_save_app_settings_overwrites_prior_value(tmp_db):
    db.save_app_settings({"timezone": "UTC"})
    db.save_app_settings({"timezone": "America/Chicago"})

    assert db.get_app_settings() == {"timezone": "America/Chicago"}


def test_save_app_settings_none_value_clears_key(tmp_db):
    db.save_app_settings({"timezone": "UTC", "ai_model": "openai/gpt-5"})
    db.save_app_settings({"timezone": None})

    assert db.get_app_settings() == {"ai_model": "openai/gpt-5"}
