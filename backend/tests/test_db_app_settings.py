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


def test_secret_app_settings_round_trip_through_get_app_settings(tmp_db):
    db.save_app_settings({"anthropic_api_key": "sk-secret"})

    assert db.get_app_settings() == {"anthropic_api_key": "sk-secret"}


def test_secret_app_settings_are_encrypted_on_disk(tmp_db):
    import sqlite3

    db.save_app_settings({"anthropic_api_key": "sk-secret"})

    with sqlite3.connect(tmp_db) as conn:
        stored = conn.execute("SELECT value FROM app_settings WHERE key = 'anthropic_api_key'").fetchone()[0]

    assert stored != "sk-secret"
    assert "sk-secret" not in stored


def test_non_secret_app_settings_are_stored_as_plaintext(tmp_db):
    import sqlite3

    db.save_app_settings({"timezone": "America/Chicago"})

    with sqlite3.connect(tmp_db) as conn:
        stored = conn.execute("SELECT value FROM app_settings WHERE key = 'timezone'").fetchone()[0]

    assert stored == "America/Chicago"
