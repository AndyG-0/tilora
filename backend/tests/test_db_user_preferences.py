from __future__ import annotations

from app.storage import db

_DEFAULTS = {
    "theme": "dark",
    "voice_provider": "browser",
    "voice_id": "",
    "voice_name": "",
    "locale": "en",
    "location": None,
}


def test_get_user_preferences_returns_defaults_when_unset(tmp_db):
    assert db.get_user_preferences("alice") == _DEFAULTS


def test_save_user_preferences_round_trips(tmp_db):
    result = db.save_user_preferences("alice", {"theme": "light"})

    assert result == {**_DEFAULTS, "theme": "light"}
    assert db.get_user_preferences("alice") == {**_DEFAULTS, "theme": "light"}


def test_save_user_preferences_merges_rather_than_overwrites(tmp_db):
    db.save_user_preferences("alice", {"theme": "light"})

    result = db.save_user_preferences("alice", {"some_other_key": "value"})

    assert result == {**_DEFAULTS, "theme": "light", "some_other_key": "value"}


def test_user_preferences_are_isolated_per_user(tmp_db):
    db.save_user_preferences("alice", {"theme": "light"})

    assert db.get_user_preferences("bob") == _DEFAULTS


def test_save_user_preferences_round_trips_voice_selection(tmp_db):
    result = db.save_user_preferences("alice", {"voice_provider": "openai", "voice_id": "nova", "voice_name": ""})

    assert result == {**_DEFAULTS, "voice_provider": "openai", "voice_id": "nova"}
    assert db.get_user_preferences("alice") == {**_DEFAULTS, "voice_provider": "openai", "voice_id": "nova"}


def test_save_user_preferences_round_trips_location(tmp_db):
    location = {"query": "Fort Worth", "display_name": "Fort Worth, TX", "latitude": 32.7555, "longitude": -97.3308}

    result = db.save_user_preferences("alice", {"location": location})

    assert result == {**_DEFAULTS, "location": location}
    assert db.get_user_preferences("alice") == {**_DEFAULTS, "location": location}
