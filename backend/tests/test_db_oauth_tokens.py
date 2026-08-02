from __future__ import annotations

from app.storage import db


def test_get_oauth_tokens_returns_none_when_unset(tmp_db):
    assert db.get_oauth_tokens("google_calendar") is None


def test_save_and_get_oauth_tokens_round_trips(tmp_db):
    db.save_oauth_tokens(
        "google_calendar", refresh_token="r1", access_token="a1", expires_at="2026-01-01T00:00:00+00:00"
    )

    tokens = db.get_oauth_tokens("google_calendar")

    assert tokens == {
        "provider": "google_calendar",
        "refresh_token": "r1",
        "access_token": "a1",
        "expires_at": "2026-01-01T00:00:00+00:00",
    }


def test_save_oauth_tokens_overwrites_existing(tmp_db):
    db.save_oauth_tokens("google_calendar", refresh_token="r1", access_token="a1")
    db.save_oauth_tokens("google_calendar", refresh_token="r2", access_token="a2")

    assert db.get_oauth_tokens("google_calendar")["refresh_token"] == "r2"
    assert db.get_oauth_tokens("google_calendar")["access_token"] == "a2"


def test_save_oauth_access_token_updates_access_token_only(tmp_db):
    db.save_oauth_tokens("google_calendar", refresh_token="r1", access_token="a1", expires_at="old")

    db.save_oauth_access_token("google_calendar", "a2", "new")

    tokens = db.get_oauth_tokens("google_calendar")
    assert tokens["access_token"] == "a2"
    assert tokens["expires_at"] == "new"
    assert tokens["refresh_token"] == "r1"
