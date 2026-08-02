from __future__ import annotations

from app.storage import db


def test_get_user_preferences_returns_defaults_when_unset(tmp_db):
    assert db.get_user_preferences("alice") == {"theme": "dark"}


def test_save_user_preferences_round_trips(tmp_db):
    result = db.save_user_preferences("alice", {"theme": "light"})

    assert result == {"theme": "light"}
    assert db.get_user_preferences("alice") == {"theme": "light"}


def test_save_user_preferences_merges_rather_than_overwrites(tmp_db):
    db.save_user_preferences("alice", {"theme": "light"})

    result = db.save_user_preferences("alice", {"some_other_key": "value"})

    assert result == {"theme": "light", "some_other_key": "value"}


def test_user_preferences_are_isolated_per_user(tmp_db):
    db.save_user_preferences("alice", {"theme": "light"})

    assert db.get_user_preferences("bob") == {"theme": "dark"}
