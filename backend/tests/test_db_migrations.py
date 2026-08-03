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


def _legacy_db_at_version_2(db_path, users=(), widget_settings=(), custom_widgets=()):
    """A DB shaped like one that already ran migrations 001+002 (users has a
    role column, no widget_user_settings table yet) — the starting point for
    exercising migration 003 in isolation."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            avatar TEXT,
            pin_hash TEXT,
            pin_salt TEXT,
            pin_iterations INTEGER,
            created_at TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member'
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
        CREATE TABLE widget_settings (
            widget_id TEXT PRIMARY KEY,
            settings TEXT NOT NULL
        );
        CREATE TABLE custom_widgets (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            layout TEXT NOT NULL,
            tab TEXT
        );
    """)
    conn.executemany(
        "INSERT INTO users (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at, role) "
        "VALUES (?, ?, NULL, NULL, NULL, NULL, ?, ?)",
        users,
    )
    conn.executemany("INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?)", widget_settings)
    conn.executemany("INSERT INTO custom_widgets (id, type, layout, tab) VALUES (?, ?, '{}', NULL)", custom_widgets)
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()


def test_migration_003_copies_personal_scope_widget_settings_to_every_existing_user(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_2(
        db_path,
        users=[
            ("alice", "Alice", "2026-01-01T00:00:00Z", "admin"),
            ("bob", "Bob", "2026-01-02T00:00:00Z", "member"),
        ],
        widget_settings=[("rss", '{"feeds": [{"url": "https://example.com/feed"}]}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "rss") == {"feeds": [{"url": "https://example.com/feed"}]}
    assert db.get_widget_user_settings("bob", "rss") == {"feeds": [{"url": "https://example.com/feed"}]}
    # The original global row is left in place, not deleted.
    assert db.get_widget_settings("rss") == {"feeds": [{"url": "https://example.com/feed"}]}


def test_migration_003_ignores_network_scope_widget_settings(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_2(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("synology", '{"host": "nas.local"}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "synology") is None


def test_migration_003_detects_personal_scope_via_custom_widget_type(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_2(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("rss-abc12345", '{"feeds": []}')],
        custom_widgets=[("rss-abc12345", "rss")],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "rss-abc12345") == {"feeds": []}


def test_migration_003_skips_users_created_after_the_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_2(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("rss", '{"feeds": []}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    db.create_user("carol", "Carol", None, None, None, None, "2026-03-01T00:00:00Z")

    assert db.get_widget_user_settings("carol", "rss") is None


def test_migration_003_is_a_no_op_on_a_fresh_install(tmp_db):
    # No users, no widget_settings — just confirms the migration doesn't
    # blow up when both source tables it reads from are empty.
    db.init_db()
    assert db.get_widget_user_settings("nobody", "rss") is None
