from __future__ import annotations

from app.storage import db


def test_get_widget_user_settings_returns_none_when_unset(tmp_db):
    assert db.get_widget_user_settings("alice", "rss") is None


def test_save_then_get_widget_user_settings_round_trips(tmp_db):
    db.save_widget_user_settings("alice", "rss", {"feeds": [{"url": "https://example.com/feed"}]})

    assert db.get_widget_user_settings("alice", "rss") == {"feeds": [{"url": "https://example.com/feed"}]}


def test_save_widget_user_settings_overwrites_prior_value_for_same_user_and_widget(tmp_db):
    db.save_widget_user_settings("alice", "rss", {"feeds": []})
    db.save_widget_user_settings("alice", "rss", {"feeds": [{"url": "https://example.com/feed"}]})

    assert db.get_widget_user_settings("alice", "rss") == {"feeds": [{"url": "https://example.com/feed"}]}


def test_widget_user_settings_are_independent_per_user_for_the_same_widget(tmp_db):
    db.save_widget_user_settings("alice", "rss", {"feeds": [{"url": "https://alice.example.com/feed"}]})
    db.save_widget_user_settings("bob", "rss", {"feeds": [{"url": "https://bob.example.com/feed"}]})

    assert db.get_widget_user_settings("alice", "rss") == {"feeds": [{"url": "https://alice.example.com/feed"}]}
    assert db.get_widget_user_settings("bob", "rss") == {"feeds": [{"url": "https://bob.example.com/feed"}]}


def test_widget_user_settings_are_independent_per_widget_for_the_same_user(tmp_db):
    db.save_widget_user_settings("alice", "rss", {"feeds": []})
    db.save_widget_user_settings("alice", "calendar", {"calendar_ids": ["primary"]})

    assert db.get_widget_user_settings("alice", "rss") == {"feeds": []}
    assert db.get_widget_user_settings("alice", "calendar") == {"calendar_ids": ["primary"]}


def test_delete_widget_user_settings_for_widget_removes_every_users_row(tmp_db):
    db.save_widget_user_settings("alice", "rss", {"feeds": []})
    db.save_widget_user_settings("bob", "rss", {"feeds": []})
    db.save_widget_user_settings("alice", "calendar", {"calendar_ids": ["primary"]})

    db.delete_widget_user_settings_for_widget("rss")

    assert db.get_widget_user_settings("alice", "rss") is None
    assert db.get_widget_user_settings("bob", "rss") is None
    # Unrelated widget for the same user is untouched.
    assert db.get_widget_user_settings("alice", "calendar") == {"calendar_ids": ["primary"]}


def test_delete_widget_user_settings_for_user_removes_every_widget_for_that_user(tmp_db):
    db.save_widget_user_settings("alice", "rss", {"feeds": []})
    db.save_widget_user_settings("alice", "calendar", {"calendar_ids": ["primary"]})
    db.save_widget_user_settings("bob", "rss", {"feeds": []})

    db.delete_widget_user_settings_for_user("alice")

    assert db.get_widget_user_settings("alice", "rss") is None
    assert db.get_widget_user_settings("alice", "calendar") is None
    # Unrelated user's row is untouched.
    assert db.get_widget_user_settings("bob", "rss") == {"feeds": []}


def test_delete_user_cascades_to_widget_user_settings(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.save_widget_user_settings("alice", "rss", {"feeds": []})

    db.delete_user("alice")

    assert db.get_widget_user_settings("alice", "rss") is None
