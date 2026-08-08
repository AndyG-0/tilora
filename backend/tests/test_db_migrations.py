from __future__ import annotations

import sqlite3

import pytest

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
        widget_settings=[("calendar", '{"ics_url": "https://example.com/cal.ics"}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "calendar") == {"ics_url": "https://example.com/cal.ics"}
    assert db.get_widget_user_settings("bob", "calendar") == {"ics_url": "https://example.com/cal.ics"}
    # The original global row is left in place, not deleted.
    assert db.get_widget_settings("calendar") == {"ics_url": "https://example.com/cal.ics"}


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
        widget_settings=[("calendar-abc12345", '{"ics_url": ""}')],
        custom_widgets=[("calendar-abc12345", "calendar")],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "calendar-abc12345") == {"ics_url": ""}


def test_migration_003_skips_users_created_after_the_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_2(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("calendar", '{"ics_url": ""}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    db.create_user("carol", "Carol", None, None, None, None, "2026-03-01T00:00:00Z")

    assert db.get_widget_user_settings("carol", "calendar") is None


def test_migration_003_is_a_no_op_on_a_fresh_install(tmp_db):
    # No users, no widget_settings — just confirms the migration doesn't
    # blow up when both source tables it reads from are empty.
    db.init_db()
    assert db.get_widget_user_settings("nobody", "calendar") is None


def _legacy_db_at_version_3(db_path, custom_widgets=(), widget_settings=()):
    """A DB shaped like one that already ran migrations 001-003 (full schema,
    no `container` merge yet) — the starting point for exercising migration
    004 in isolation."""
    conn = sqlite3.connect(db_path)
    conn.executescript(db._SCHEMA)
    conn.executemany("INSERT INTO custom_widgets (id, type, layout, tab) VALUES (?, ?, '{}', NULL)", custom_widgets)
    conn.executemany("INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?)", widget_settings)
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()


def test_migration_004_rewrites_custom_widget_type_to_container(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_3(db_path, custom_widgets=[("podman-abc12345", "podman")])

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    widgets = {w["id"]: w["type"] for w in db.list_custom_widgets()}
    assert widgets == {"podman-abc12345": "container"}
    assert db.get_widget_settings("podman-abc12345") == {"engine": "podman"}


def test_migration_004_preserves_existing_settings_overrides(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_3(
        db_path,
        custom_widgets=[("docker-def67890", "docker")],
        widget_settings=[("docker-def67890", '{"connection": "tcp", "host": "nas.local", "port": 2375}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_settings("docker-def67890") == {
        "connection": "tcp",
        "host": "nas.local",
        "port": 2375,
        "engine": "docker",
    }


def test_migration_004_ignores_other_widget_types(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_3(db_path, custom_widgets=[("rss-abc12345", "rss")])

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    widgets = {w["id"]: w["type"] for w in db.list_custom_widgets()}
    assert widgets == {"rss-abc12345": "rss"}
    assert db.get_widget_settings("rss-abc12345") is None


def test_migration_004_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_3(db_path, custom_widgets=[("podman-abc12345", "podman")])

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    db.init_db()

    widgets = {w["id"]: w["type"] for w in db.list_custom_widgets()}
    assert widgets == {"podman-abc12345": "container"}
    assert db.get_widget_settings("podman-abc12345") == {"engine": "podman"}


def _legacy_db_at_version_4(db_path, users=(), widget_settings=(), custom_widgets=()):
    """A DB shaped like one that already ran migrations 001-004 (full schema,
    no sports/weather personal-scope seeding yet) — the starting point for
    exercising migration 005 in isolation."""
    conn = sqlite3.connect(db_path)
    conn.executescript(db._SCHEMA)
    conn.executemany(
        "INSERT INTO users (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at, role) "
        "VALUES (?, ?, NULL, NULL, NULL, NULL, ?, ?)",
        users,
    )
    conn.executemany("INSERT INTO custom_widgets (id, type, layout, tab) VALUES (?, ?, '{}', NULL)", custom_widgets)
    conn.executemany("INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?)", widget_settings)
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()


def test_migration_005_copies_sports_and_weather_settings_to_every_existing_user(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_4(
        db_path,
        users=[
            ("alice", "Alice", "2026-01-01T00:00:00Z", "admin"),
            ("bob", "Bob", "2026-01-02T00:00:00Z", "member"),
        ],
        widget_settings=[
            ("sports", '{"teams": [{"league": "nfl", "team": "PHI"}]}'),
            ("weather", '{"location_name": "Fort Worth, TX"}'),
        ],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "sports") == {"teams": [{"league": "nfl", "team": "PHI"}]}
    assert db.get_widget_user_settings("bob", "sports") == {"teams": [{"league": "nfl", "team": "PHI"}]}
    assert db.get_widget_user_settings("alice", "weather") == {"location_name": "Fort Worth, TX"}
    assert db.get_widget_user_settings("bob", "weather") == {"location_name": "Fort Worth, TX"}
    # The original global rows are left in place, not deleted.
    assert db.get_widget_settings("sports") == {"teams": [{"league": "nfl", "team": "PHI"}]}


def test_migration_005_ignores_network_scope_widget_settings(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_4(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("synology", '{"host": "nas.local"}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "synology") is None


def test_migration_005_detects_sports_via_custom_widget_type(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_4(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("sports-abc12345", '{"teams": []}')],
        custom_widgets=[("sports-abc12345", "sports")],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "sports-abc12345") == {"teams": []}


def test_migration_005_skips_users_created_after_the_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_4(
        db_path,
        users=[("alice", "Alice", "2026-01-01T00:00:00Z", "admin")],
        widget_settings=[("sports", '{"teams": []}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    db.create_user("carol", "Carol", None, None, None, None, "2026-03-01T00:00:00Z")

    assert db.get_widget_user_settings("carol", "sports") is None


def test_migration_005_is_a_no_op_on_a_fresh_install(tmp_db):
    db.init_db()
    assert db.get_widget_user_settings("nobody", "sports") is None


def _legacy_db_at_version_5(db_path, widget_user_settings=(), custom_widgets=()):
    """A DB shaped like one that already ran migrations 001-005 (full
    schema, RSS feeds still inline in each tile's own settings) — the
    starting point for exercising migration 006 in isolation."""
    conn = sqlite3.connect(db_path)
    conn.executescript(db._SCHEMA)
    conn.executemany("INSERT INTO custom_widgets (id, type, layout, tab) VALUES (?, ?, '{}', NULL)", custom_widgets)
    conn.executemany(
        "INSERT INTO widget_user_settings (user_id, widget_id, settings) VALUES (?, ?, ?)", widget_user_settings
    )
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    conn.close()


def test_migration_006_moves_inline_feeds_into_the_user_catalog(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_5(
        db_path,
        widget_user_settings=[
            (
                "alice",
                "rss",
                '{"title": "Headlines", "feeds": [{"url": "https://a.example/feed.xml", "name": "A"}], '
                '"item_limit": 5}',
            )
        ],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    feeds = db.list_rss_feeds("alice")
    assert len(feeds) == 1
    assert feeds[0]["url"] == "https://a.example/feed.xml"
    assert feeds[0]["name"] == "A"
    assert feeds[0]["item_limit"] == 10

    settings = db.get_widget_user_settings("alice", "rss")
    assert settings == {"title": "Headlines", "feed_ids": [feeds[0]["id"]]}


def test_migration_006_detects_rss_via_custom_widget_type(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_5(
        db_path,
        widget_user_settings=[("alice", "rss-abc12345", '{"feeds": [{"url": "https://a.example/feed.xml"}]}')],
        custom_widgets=[("rss-abc12345", "rss")],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_user_settings("alice", "rss-abc12345") == {"feed_ids": [db.list_rss_feeds("alice")[0]["id"]]}


def test_migration_006_ignores_non_rss_widgets(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_5(
        db_path,
        widget_user_settings=[("alice", "sports", '{"teams": []}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.list_rss_feeds("alice") == []
    assert db.get_widget_user_settings("alice", "sports") == {"teams": []}


def test_migration_006_skips_rows_already_migrated(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_5(
        db_path,
        widget_user_settings=[("alice", "rss", '{"title": "Headlines", "feed_ids": [1]}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.list_rss_feeds("alice") == []
    assert db.get_widget_user_settings("alice", "rss") == {"title": "Headlines", "feed_ids": [1]}


def test_migration_006_reuses_an_existing_catalog_entry_for_the_same_url(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_5(
        db_path,
        widget_user_settings=[
            ("alice", "rss", '{"feeds": [{"url": "https://a.example/feed.xml"}]}'),
            ("alice", "rss-abc12345", '{"feeds": [{"url": "https://a.example/feed.xml"}]}'),
        ],
        custom_widgets=[("rss-abc12345", "rss")],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert len(db.list_rss_feeds("alice")) == 1
    shared_id = db.list_rss_feeds("alice")[0]["id"]
    assert db.get_widget_user_settings("alice", "rss") == {"feed_ids": [shared_id]}
    assert db.get_widget_user_settings("alice", "rss-abc12345") == {"feed_ids": [shared_id]}


def test_migration_006_is_a_no_op_on_a_fresh_install(tmp_db):
    db.init_db()
    assert db.list_rss_feeds("nobody") == []


def test_a_failed_callable_migration_leaves_user_version_at_the_last_completed_one(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    def _mig_a(conn):
        conn.execute("CREATE TABLE test_marker (name TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO test_marker (name) VALUES ('a')")

    def _mig_b_fails(conn):
        conn.execute("INSERT INTO test_marker (name) VALUES ('b')")
        raise RuntimeError("boom")

    def _mig_c(conn):
        conn.execute("INSERT INTO test_marker (name) VALUES ('c')")

    monkeypatch.setattr(db, "_MIGRATIONS", (_mig_a, _mig_b_fails, _mig_c))

    with pytest.raises(RuntimeError, match="boom"):
        db.init_db()

    conn = sqlite3.connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    names = {row[0] for row in conn.execute("SELECT name FROM test_marker")}
    conn.close()

    # mig_a's write committed and its version bump stuck; mig_b's write (and
    # its own version bump) rolled back together since it raised; mig_c never ran.
    assert version == 1
    assert names == {"a"}


def test_retrying_after_a_failed_callable_migration_resumes_from_where_it_stopped(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    def _mig_a(conn):
        conn.execute("CREATE TABLE test_marker (name TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO test_marker (name) VALUES ('a')")

    attempt = {"n": 0}

    def _mig_b(conn):
        attempt["n"] += 1
        conn.execute("INSERT INTO test_marker (name) VALUES ('b')")
        if attempt["n"] == 1:
            raise RuntimeError("boom")

    def _mig_c(conn):
        conn.execute("INSERT INTO test_marker (name) VALUES ('c')")

    monkeypatch.setattr(db, "_MIGRATIONS", (_mig_a, _mig_b, _mig_c))

    with pytest.raises(RuntimeError, match="boom"):
        db.init_db()

    # Retrying re-opens the same (unfinished) database. mig_a must not rerun
    # (it would hit a PRIMARY KEY conflict re-inserting 'a') and mig_b's
    # rolled-back partial write from the failed attempt must not collide
    # with its retry.
    db.init_db()

    conn = sqlite3.connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    names = [row[0] for row in conn.execute("SELECT name FROM test_marker ORDER BY rowid")]
    conn.close()

    assert version == 3
    assert names == ["a", "b", "c"]


def test_a_failed_script_migration_rolls_back_completely(tmp_path, monkeypatch):
    """Regression test for the specific crash-unsafety this migration runner
    fixes: `executescript()` implicitly commits any pending transaction
    before it runs, so a `BEGIN`/`COMMIT` issued via separate `conn.execute`
    calls around it would be silently defeated. The runner instead bakes
    `BEGIN`/`COMMIT` directly into the script text — this confirms that a
    later statement failing still rolls back everything the script already
    did (the CREATE TABLE and first INSERT below), not just the version bump.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    broken_script = """
CREATE TABLE test_marker (name TEXT PRIMARY KEY);
INSERT INTO test_marker (name) VALUES ('x');
INSERT INTO this_table_does_not_exist (name) VALUES ('y');
"""
    monkeypatch.setattr(db, "_MIGRATIONS", (broken_script,))

    with pytest.raises(sqlite3.OperationalError):
        db.init_db()

    conn = sqlite3.connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    conn.close()

    assert version == 0
    assert "test_marker" not in tables
