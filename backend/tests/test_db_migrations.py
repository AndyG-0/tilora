from __future__ import annotations

import sqlite3

from app.storage import db


def test_fresh_install_ends_with_zero_users_and_zero_admins(tmp_db):
    assert db.list_users() == []


def test_fresh_install_users_table_has_a_role_column(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")

    assert db.get_user("alice")["role"] == "member"


def test_upgrade_from_a_pre_role_db_promotes_the_oldest_user_to_admin(tmp_path, monkeypatch):
    """Simulates an install that already ran migration 001 (users/devices
    exist, seeded with the old unconditional "default" rows) before the
    role column/migration 002 ever shipped.
    """
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            avatar TEXT,
            pin_hash TEXT,
            pin_salt TEXT,
            pin_iterations INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE widget_layout (
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            widget_id TEXT NOT NULL,
            layout TEXT NOT NULL,
            PRIMARY KEY (user_id, device_id, widget_id)
        );
    """)
    conn.executemany(
        "INSERT INTO users (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("default", "Default", None, None, None, None, "2026-01-01T00:00:00Z"),
            ("alice", "Alice", None, None, None, None, "2026-02-01T00:00:00Z"),
        ],
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    users = {u["id"]: u["role"] for u in db.list_users()}
    assert users == {"default": "admin", "alice": "member"}


def test_upgrade_with_multiple_pre_existing_users_promotes_only_the_oldest(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            avatar TEXT,
            pin_hash TEXT,
            pin_salt TEXT,
            pin_iterations INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE widget_layout (
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            widget_id TEXT NOT NULL,
            layout TEXT NOT NULL,
            PRIMARY KEY (user_id, device_id, widget_id)
        );
    """)
    conn.executemany(
        "INSERT INTO users (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("bob", "Bob", None, None, None, None, "2026-03-01T00:00:00Z"),
            ("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z"),
            ("carol", "Carol", None, None, None, None, "2026-02-01T00:00:00Z"),
        ],
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    users = {u["id"]: u["role"] for u in db.list_users()}
    assert users == {"alice": "admin", "bob": "member", "carol": "member"}


def test_migrations_are_idempotent(tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z", role="admin")

    db.init_db()
    db.init_db()

    users = {u["id"]: u["role"] for u in db.list_users()}
    assert users == {"alice": "admin"}
