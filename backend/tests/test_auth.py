from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app import auth
from app.storage import db


def test_hash_pin_then_verify_pin_round_trips():
    pin_hash, pin_salt, iterations = auth.hash_pin("1234")

    assert auth.verify_pin("1234", pin_hash, pin_salt, iterations) is True


def test_verify_pin_rejects_wrong_pin():
    pin_hash, pin_salt, iterations = auth.hash_pin("1234")

    assert auth.verify_pin("9999", pin_hash, pin_salt, iterations) is False


def test_hash_pin_uses_a_fresh_salt_each_call():
    hash_a, salt_a, _ = auth.hash_pin("1234")
    hash_b, salt_b, _ = auth.hash_pin("1234")

    assert salt_a != salt_b
    assert hash_a != hash_b


def test_new_token_returns_distinct_unguessable_values():
    assert auth.new_token() != auth.new_token()


def test_hash_token_is_deterministic_and_not_the_raw_value():
    assert auth._hash_token("abc") == auth._hash_token("abc")
    assert auth._hash_token("abc") != "abc"


def test_device_and_session_rows_store_a_hash_not_the_raw_cookie_value(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2020-01-01T00:00:00Z")
    db.create_device(auth._hash_token("raw-device-token"), "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    db.create_session(
        auth._hash_token("raw-session-token"), "alice", "dev1", "2020-01-01T00:00:00Z", auth.session_expiry()
    )

    assert db.get_device("raw-device-token") is None
    assert db.get_session("raw-session-token") is None


class _FakeRequest:
    def __init__(self, cookies: dict[str, str]):
        self.cookies = cookies


async def test_get_current_device_raises_401_without_a_cookie(tmp_db):
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_device(_FakeRequest({}))
    assert exc_info.value.status_code == 401


async def test_get_current_device_raises_401_for_an_unknown_device_id(tmp_db):
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_device(_FakeRequest({auth.DEVICE_COOKIE_NAME: "nope"}))
    assert exc_info.value.status_code == 401


async def test_get_current_device_returns_the_device_and_bumps_last_seen(tmp_db):
    # The devices table is keyed by a hash of the bearer token, not the raw
    # cookie value — store the hash, present the raw token as the cookie.
    hashed_id = auth._hash_token("dev1")
    db.create_device(hashed_id, "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")

    device = await auth.get_current_device(_FakeRequest({auth.DEVICE_COOKIE_NAME: "dev1"}))

    assert device["id"] == hashed_id
    # The dependency's own return value is a pre-touch snapshot; the bump is
    # a side effect visible on the next read, not on this one.
    assert db.get_device(hashed_id)["last_seen_at"] != "2020-01-01T00:00:00Z"


async def test_get_current_session_raises_401_without_a_cookie(tmp_db):
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_session(_FakeRequest({}))
    assert exc_info.value.status_code == 401


async def test_get_current_session_raises_401_for_an_expired_session(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2020-01-01T00:00:00Z")
    db.create_device("dev1", "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    expired = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    db.create_session(auth._hash_token("sess1"), "alice", "dev1", "2020-01-01T00:00:00Z", expired)

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_session(_FakeRequest({auth.SESSION_COOKIE_NAME: "sess1"}))
    assert exc_info.value.status_code == 401


async def test_get_current_session_returns_the_session_when_valid(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2020-01-01T00:00:00Z")
    db.create_device("dev1", "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    hashed_session_id = auth._hash_token("sess1")
    db.create_session(hashed_session_id, "alice", "dev1", "2020-01-01T00:00:00Z", auth.session_expiry())

    session = await auth.get_current_session(_FakeRequest({auth.SESSION_COOKIE_NAME: "sess1"}))

    assert session["id"] == hashed_session_id
    assert session["user_id"] == "alice"


async def test_get_current_user_resolves_from_a_valid_session(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2020-01-01T00:00:00Z")
    db.create_device("dev1", "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    db.create_session(auth._hash_token("sess1"), "alice", "dev1", "2020-01-01T00:00:00Z", auth.session_expiry())
    session = await auth.get_current_session(_FakeRequest({auth.SESSION_COOKIE_NAME: "sess1"}))

    user = await auth.get_current_user(session)

    assert user["id"] == "alice"


async def test_get_current_user_raises_401_when_the_user_row_is_gone(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2020-01-01T00:00:00Z")
    db.create_device("dev1", "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    db.create_session(auth._hash_token("sess1"), "alice", "dev1", "2020-01-01T00:00:00Z", auth.session_expiry())
    session = await auth.get_current_session(_FakeRequest({auth.SESSION_COOKIE_NAME: "sess1"}))
    db.delete_user("alice")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(session)
    assert exc_info.value.status_code == 401


def _seed_pre_hashing_row(db_path, *, device_id="dev1", user_id="alice", session_id="sess1"):
    """Inserts a devices/users/sessions row the old (pre-v0.15.0) way: the
    raw bearer token stored directly as the primary key, rather than a hash
    of it. Used to simulate a database from before migration 019 rehashed
    these ids in place."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO devices (id, name, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
            (device_id, "Kitchen", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO users (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at, role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, "Alice", None, None, None, None, "2020-01-01T00:00:00Z", "member"),
        )
        conn.execute(
            "INSERT INTO sessions (id, user_id, device_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, device_id, "2020-01-01T00:00:00Z", "2999-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO custom_widgets (id, type, layout, tab, owner_user_id, owner_device_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("widget1", "clock", "{}", None, user_id, device_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_migration_019_rehashes_pre_upgrade_device_and_session_ids(tmp_db_pre_token_hashing):
    _seed_pre_hashing_row(tmp_db_pre_token_hashing)

    db.init_db()

    hashed_device_id = auth._hash_token("dev1")
    hashed_session_id = auth._hash_token("sess1")
    assert db.get_device("dev1") is None
    assert db.get_device(hashed_device_id) is not None
    assert db.get_session("sess1") is None
    assert db.get_session(hashed_session_id) is not None
    # The device-scoped foreign-key-ish column on custom_widgets must follow
    # the id rewrite too, or a pre-upgrade private tile would silently stop
    # matching its owning device forever.
    assert db.list_custom_widgets()[0]["owner_device_id"] == hashed_device_id


async def test_get_current_device_resolves_a_pre_upgrade_cookie_without_duplicating(tmp_db_pre_token_hashing):
    _seed_pre_hashing_row(tmp_db_pre_token_hashing)
    db.init_db()

    device = await auth.get_current_device(_FakeRequest({auth.DEVICE_COOKIE_NAME: "dev1"}))

    assert device["id"] == auth._hash_token("dev1")
    assert len(db.list_devices()) == 1


async def test_get_current_session_resolves_a_pre_upgrade_cookie(tmp_db_pre_token_hashing):
    _seed_pre_hashing_row(tmp_db_pre_token_hashing)
    db.init_db()

    session = await auth.get_current_session(_FakeRequest({auth.SESSION_COOKIE_NAME: "sess1"}))

    assert session["id"] == auth._hash_token("sess1")
    assert session["user_id"] == "alice"


async def test_get_current_admin_returns_the_user_when_role_is_admin(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2020-01-01T00:00:00Z", role="admin")
    user = db.get_user("alice")

    admin = await auth.get_current_admin(user)

    assert admin["id"] == "alice"


async def test_get_current_admin_raises_403_for_a_member(tmp_db):
    db.create_user("bob", "Bob", None, None, None, None, "2020-01-01T00:00:00Z", role="member")
    user = db.get_user("bob")

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_admin(user)
    assert exc_info.value.status_code == 403


def test_is_locked_out_is_false_with_no_recorded_failures():
    assert auth.is_locked_out("alice") is False


def test_is_locked_out_becomes_true_after_max_failed_attempts():
    for _ in range(auth._MAX_FAILED_ATTEMPTS):
        auth.record_failed_login("alice")

    assert auth.is_locked_out("alice") is True


def test_is_locked_out_stays_false_below_the_threshold():
    for _ in range(auth._MAX_FAILED_ATTEMPTS - 1):
        auth.record_failed_login("alice")

    assert auth.is_locked_out("alice") is False


def test_record_successful_login_clears_failed_attempts():
    for _ in range(auth._MAX_FAILED_ATTEMPTS):
        auth.record_failed_login("alice")

    auth.record_successful_login("alice")

    assert auth.is_locked_out("alice") is False


def test_lockout_expires_after_the_window_passes(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])

    for _ in range(auth._MAX_FAILED_ATTEMPTS):
        auth.record_failed_login("alice")
    assert auth.is_locked_out("alice") is True

    clock[0] += auth._LOCKOUT_WINDOW_SECONDS + 1

    assert auth.is_locked_out("alice") is False


def test_lockout_is_scoped_per_user_id():
    for _ in range(auth._MAX_FAILED_ATTEMPTS):
        auth.record_failed_login("alice")

    assert auth.is_locked_out("bob") is False
