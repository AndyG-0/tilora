from __future__ import annotations

import re
import sqlite3

import pytest
import yaml

from app import config
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
    # Migration 007 (which also runs as part of the same init_db() chain)
    # then extracts the connection fields migration 004 wrote into a
    # network_integrations row, leaving only the reference behind.
    settings = db.get_widget_settings("podman-abc12345")
    assert set(settings) == {"network_integration_id"}
    integration = db.get_network_integration(settings["network_integration_id"])
    assert integration["settings"]["engine"] == "podman"


def test_migration_004_preserves_existing_settings_overrides(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_3(
        db_path,
        custom_widgets=[("docker-def67890", "docker")],
        widget_settings=[("docker-def67890", '{"connection": "tcp", "host": "nas.local", "port": 2375}')],
    )

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    settings = db.get_widget_settings("docker-def67890")
    assert set(settings) == {"network_integration_id"}
    integration = db.get_network_integration(settings["network_integration_id"])
    assert integration["settings"] == {
        "connection": "tcp",
        "host": "nas.local",
        "port": 2375,
        "engine": "docker",
        "socket_path": "/var/run/docker.sock",
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
    settings = db.get_widget_settings("podman-abc12345")
    assert set(settings) == {"network_integration_id"}
    integration = db.get_network_integration(settings["network_integration_id"])
    assert integration["settings"]["engine"] == "podman"


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


def _write_dashboard_yaml(tmp_path, widgets):
    """A minimal dashboard.yaml with just the given widgets, for exercising
    migration 007 (which — unlike migrations 003/005/006 — has to read
    dashboard.yaml, not just the DB) without touching the real, git-tracked
    backend/config/dashboard.yaml."""
    config_path = tmp_path / "dashboard.yaml"
    config_path.write_text(yaml.safe_dump({"widgets": widgets}))
    return config_path


def _widget_entry(widget_id, type_, settings=None):
    return {
        "id": widget_id,
        "type": type_,
        "enabled": True,
        "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "settings": settings or {},
    }


def _legacy_db_at_version_6(db_path, widget_settings=()):
    """A DB shaped like one that already ran migrations 001-006 (full
    schema, connection settings for the six LAN-device plugins still inline
    in dashboard.yaml/widget_settings) — the starting point for exercising
    migration 007 in isolation."""
    conn = sqlite3.connect(db_path)
    conn.executescript(db._SCHEMA)
    conn.executemany("INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?)", widget_settings)
    conn.execute("PRAGMA user_version = 6")
    conn.commit()
    conn.close()


def test_migration_007_creates_singleton_integration_from_yaml_defaults(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_6(db_path)
    _write_dashboard_yaml(tmp_path, [_widget_entry("pihole", "pihole", {"host": "pi.local", "port": 8080})])
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", tmp_path / "dashboard.yaml")

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    integration = db.get_network_integration("pihole")
    assert integration["type"] == "pihole"
    assert integration["settings"]["host"] == "pi.local"
    assert integration["settings"]["port"] == 8080
    # No widget_settings row existed for "pihole" before the migration, so
    # there's nothing to strip connection keys out of.
    assert db.get_widget_settings("pihole") is None


def test_migration_007_db_override_wins_over_yaml(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_6(db_path, widget_settings=[("pihole", '{"host": "db.local"}')])
    _write_dashboard_yaml(tmp_path, [_widget_entry("pihole", "pihole", {"host": "yaml.local"})])
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", tmp_path / "dashboard.yaml")

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    integration = db.get_network_integration("pihole")
    assert integration["settings"]["host"] == "db.local"
    # The DB override's connection key was extracted into the integration
    # row and stripped from the widget's own settings, leaving the row
    # empty (it still exists — only its content was rewritten).
    assert db.get_widget_settings("pihole") == {}


def test_migration_007_preserves_non_connection_overrides_on_the_widget(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_6(
        db_path, widget_settings=[("hdhomerun", '{"tuner_host": "hdhr.local", "playback_mode": "direct"}')]
    )
    _write_dashboard_yaml(tmp_path, [_widget_entry("hdhomerun", "hdhomerun")])
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", tmp_path / "dashboard.yaml")

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    integration = db.get_network_integration("hdhomerun")
    assert integration["settings"]["tuner_host"] == "hdhr.local"
    # "playback_mode" isn't a connection key (it's not in
    # HDHomeRunPlugin.network_default_settings), so it stays behind on the
    # widget's own settings row instead of being migrated.
    assert db.get_widget_settings("hdhomerun") == {"playback_mode": "direct"}


def test_migration_007_gives_each_container_widget_its_own_integration(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_6(db_path)
    _write_dashboard_yaml(
        tmp_path,
        [
            _widget_entry("docker", "container", {"engine": "docker", "host": "nas.local"}),
            _widget_entry("podman", "container", {"engine": "podman", "host": "pi.local"}),
        ],
    )
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", tmp_path / "dashboard.yaml")

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    docker_settings = db.get_widget_settings("docker")
    podman_settings = db.get_widget_settings("podman")
    assert set(docker_settings) == {"network_integration_id"}
    assert set(podman_settings) == {"network_integration_id"}
    assert docker_settings["network_integration_id"] != podman_settings["network_integration_id"]

    docker_integration = db.get_network_integration(docker_settings["network_integration_id"])
    podman_integration = db.get_network_integration(podman_settings["network_integration_id"])
    assert docker_integration["settings"]["engine"] == "docker"
    assert docker_integration["settings"]["host"] == "nas.local"
    assert podman_integration["settings"]["engine"] == "podman"
    assert podman_integration["settings"]["host"] == "pi.local"


def test_migration_007_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_6(db_path)
    _write_dashboard_yaml(
        tmp_path,
        [
            _widget_entry("pihole", "pihole", {"host": "pi.local"}),
            _widget_entry("docker", "container", {"engine": "docker"}),
        ],
    )
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", tmp_path / "dashboard.yaml")

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    db.init_db()

    assert len(db.list_network_integrations("pihole")) == 1
    assert len(db.list_network_integrations("container")) == 1
    docker_settings = db.get_widget_settings("docker")
    assert set(docker_settings) == {"network_integration_id"}


def test_migration_007_is_a_no_op_when_no_matching_widgets_exist(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _legacy_db_at_version_6(db_path)
    _write_dashboard_yaml(tmp_path, [_widget_entry("weather", "weather")])
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", tmp_path / "dashboard.yaml")

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.list_network_integrations() == []


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


# Frozen copy of `_SCHEMA` as it shipped in the v0.10.0 release (git tag
# a55a956, the last real release before migrations 009-014 were designed) —
# i.e. what any out-of-date deployment's on-disk database actually looks
# like: every table migrations 001-008 touch is already in its final shape,
# but `photo_index`/`packages` (untouched by any migration until 012/014)
# are still in their pre-user_id shape, old indexes and all. Deliberately
# not re-derived from the current `_SCHEMA` on each run — the whole point is
# to pin what a real released version looked like, so this test keeps
# proving the real upgrade path stays safe regardless of what `_SCHEMA`
# grows into next.
_V0_10_0_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    ran_at TEXT NOT NULL,
    result TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_runs_widget_id ON ai_runs (widget_id, ran_at DESC);

CREATE TABLE IF NOT EXISTS speedtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    ran_at TEXT NOT NULL,
    download_mbps REAL NOT NULL,
    upload_mbps REAL NOT NULL,
    ping_ms REAL NOT NULL,
    server_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_speedtest_runs_widget_id ON speedtest_runs (widget_id, ran_at DESC);

CREATE TABLE IF NOT EXISTS nasa_apod_fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    result TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nasa_apod_fetches_widget_id ON nasa_apod_fetches (widget_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS chores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    text TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_chores_widget_user ON chores (widget_id, user_id, completed, created_at);

CREATE TABLE IF NOT EXISTS shopping_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    text TEXT NOT NULL,
    checked INTEGER NOT NULL DEFAULT 0,
    added_by TEXT NOT NULL,
    checked_by TEXT,
    created_at TEXT NOT NULL,
    checked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_shopping_items_widget ON shopping_items (widget_id, checked, created_at);

CREATE TABLE IF NOT EXISTS widget_settings (
    widget_id TEXT PRIMARY KEY,
    settings TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS network_integrations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    settings TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_network_integrations_type ON network_integrations (type);

CREATE TABLE IF NOT EXISTS widget_layout (
    user_id TEXT NOT NULL,
    breakpoint TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    layout TEXT NOT NULL,
    PRIMARY KEY (user_id, breakpoint, widget_id)
);
CREATE INDEX IF NOT EXISTS idx_widget_layout_widget_id ON widget_layout (widget_id);

CREATE TABLE IF NOT EXISTS screensaver_settings (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    settings TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id)
);

CREATE TABLE IF NOT EXISTS widget_user_settings (
    user_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    settings TEXT NOT NULL,
    PRIMARY KEY (user_id, widget_id)
);
CREATE INDEX IF NOT EXISTS idx_widget_user_settings_widget_id ON widget_user_settings (widget_id);

CREATE TABLE IF NOT EXISTS widget_device_settings (
    device_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    settings TEXT NOT NULL,
    PRIMARY KEY (device_id, widget_id)
);
CREATE INDEX IF NOT EXISTS idx_widget_device_settings_widget_id ON widget_device_settings (widget_id);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    avatar TEXT,
    pin_hash TEXT,
    pin_salt TEXT,
    pin_iterations INTEGER,
    created_at TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member'
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_device_id ON sessions (device_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    preferences TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    dismissed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_widget_id ON alerts (widget_id, created_at DESC);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    provider TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    access_token TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS custom_widgets (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    layout TEXT NOT NULL,
    tab TEXT
);

CREATE TABLE IF NOT EXISTS removed_widget_ids (
    widget_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS photo_index (
    widget_id TEXT NOT NULL,
    photo_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    generation INTEGER NOT NULL,
    PRIMARY KEY (widget_id, photo_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_index_widget_position ON photo_index (widget_id, position);

CREATE TABLE IF NOT EXISTS photo_index_meta (
    widget_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS severe_weather_seen (
    widget_id TEXT NOT NULL,
    alert_key TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (widget_id, alert_key)
);

CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    tracking_number TEXT NOT NULL,
    carrier TEXT,
    label TEXT,
    status TEXT,
    last_event TEXT,
    eta_date TEXT,
    delivered INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_packages_widget ON packages (widget_id, delivered, eta_date);

CREATE TABLE IF NOT EXISTS rss_feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    url TEXT NOT NULL,
    name TEXT,
    item_limit INTEGER NOT NULL DEFAULT 10,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, url)
);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_user_id ON rss_feeds (user_id);
"""


def test_upgrade_from_v0_10_0_schema_runs_every_migration_cleanly(tmp_path, monkeypatch):
    """Regression test for the real crash: `sqlite3.OperationalError: no such
    column: user_id` from `init_db()` on a database that already had
    `photo_index`/`packages` in their pre-migration shape (see the
    `CREATE INDEX` comments left in `_SCHEMA` next to those two tables).
    `_V0_10_0_SCHEMA` above is what any environment still running the last
    real release has on disk right now; this proves the current code
    upgrades it all the way to the latest migration without raising, the
    same as it will need to for a real deployed instance.
    """
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_V0_10_0_SCHEMA)
    conn.execute("PRAGMA user_version = 8")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)

    db.init_db()

    conn = sqlite3.connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    photo_index_columns = {row[1] for row in conn.execute("PRAGMA table_info(photo_index)")}
    packages_columns = {row[1] for row in conn.execute("PRAGMA table_info(packages)")}
    indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    conn.close()

    assert version == len(db._MIGRATIONS)
    assert "user_id" in photo_index_columns
    assert "user_id" in packages_columns
    assert "idx_photo_index_widget_user_position" in indexes
    assert "idx_packages_widget_user" in indexes


def test_schema_indexes_never_reference_a_column_only_an_alter_migration_adds(tmp_path, monkeypatch):
    """Static guard against the same bug class recurring. Note `_SCHEMA`'s
    `CREATE TABLE IF NOT EXISTS` for `photo_index`/`packages` already lists
    `user_id` (correct — that's the final shape a brand-new install should
    get), so diffing `_SCHEMA`'s own CREATE TABLE/CREATE INDEX text against
    each other can't detect this: the bug only bites an *upgrading* database,
    where that same CREATE TABLE is a no-op and the column doesn't exist
    until its migration's `ALTER TABLE ... ADD COLUMN` runs. So instead this
    finds every (table, column) added by an ALTER-style migration and
    asserts `_SCHEMA` never indexes that column for that table — keeps
    catching this the moment a new offending index is added, with no
    per-migration maintenance required.
    """
    import inspect

    altered_columns = set(re.findall(r"ALTER TABLE (\w+) ADD COLUMN (\w+)", inspect.getsource(db)))

    offenders = []
    for index_name, table_name, columns_blob in re.findall(
        r"CREATE INDEX IF NOT EXISTS (\w+) ON (\w+) \(([^)]*)\)", db._SCHEMA
    ):
        referenced = {c.strip().split()[0] for c in columns_blob.split(",")}
        for column in referenced:
            if (table_name, column) in altered_columns:
                offenders.append((index_name, table_name, column))

    assert offenders == []


def test_migration_015_deduplicates_duplicate_device_names(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(db._SCHEMA)
    conn.executemany(
        "INSERT INTO devices (id, name, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
        [
            ("dev1", "New Device", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            ("dev2", "New Device", "2026-01-02T00:00:00Z", "2026-01-02T00:00:00Z"),
            ("dev3", "New Device", "2026-01-03T00:00:00Z", "2026-01-03T00:00:00Z"),
            ("dev4", "Tablet", "2026-01-04T00:00:00Z", "2026-01-04T00:00:00Z"),
            ("dev5", "tablet", "2026-01-05T00:00:00Z", "2026-01-05T00:00:00Z"),
        ],
    )
    conn.commit()

    db._migration_015_deduplicate_device_names(conn)
    conn.commit()

    rows = conn.execute("SELECT id, name FROM devices ORDER BY created_at ASC").fetchall()
    conn.close()

    assert rows == [
        ("dev1", "New Device"),
        ("dev2", "New Device 2"),
        ("dev3", "New Device 3"),
        ("dev4", "Tablet"),
        ("dev5", "tablet 2"),
    ]
