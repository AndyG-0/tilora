from __future__ import annotations

import sqlite3

from app.storage import db


def test_get_widget_layout_returns_none_when_unset(tmp_db):
    assert db.get_widget_layout("alice", "dev1", "wide", "clock") is None


def test_save_then_get_widget_layout_round_trips(tmp_db):
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})

    assert db.get_widget_layout("alice", "dev1", "wide", "clock") == {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}


def test_save_widget_layout_overwrites_prior_value_for_same_user_device_and_breakpoint(tmp_db):
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1})

    assert db.get_widget_layout("alice", "dev1", "wide", "clock") == {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1}


def test_widget_layout_is_independent_per_breakpoint_for_same_user_and_device(tmp_db):
    db.save_widget_layout("alice", "dev1", "narrow", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "dev1", "narrow", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("alice", "dev1", "wide", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_widget_layout_is_independent_per_user_for_same_device_and_breakpoint(tmp_db):
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("bob", "dev1", "wide", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "dev1", "wide", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("bob", "dev1", "wide", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_widget_layout_is_independent_per_device_for_same_user_and_breakpoint(tmp_db):
    # The core multi-device fix: the same user's layout on one screen must
    # not leak onto (or get overwritten by) another screen they use.
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "dev2", "wide", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "dev1", "wide", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("alice", "dev2", "wide", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_list_widget_layouts_returns_all_overrides_for_a_user_device_and_breakpoint(tmp_db):
    db.save_widget_layout("alice", "dev1", "wide", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "dev1", "wide", "weather", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "dev2", "wide", "clock", {"col": 9, "row": 9, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("bob", "dev1", "wide", "clock", {"col": 9, "row": 9, "colSpan": 1, "rowSpan": 1})

    layouts = db.list_widget_layouts("alice", "dev1", "wide")

    assert layouts == {
        "clock": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "weather": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1},
    }


def test_migration_reseats_pre_existing_single_user_layout_under_default_user_device_and_wide_breakpoint(
    tmp_path, monkeypatch
):
    """Simulates upgrading a pre-multi-user install: an old-shape `widget_layout`
    table (widget_id PRIMARY KEY, no user_id/device_id) already has live rows,
    and a device from that same era is already registered, before `init_db()`
    ever runs the new schema/migrations against this file.

    Migration 001 re-keys these rows under a "default" user/device id.
    Migration 008 then collapses device_id into breakpoint, landing
    everything under "wide". Migration 009 re-adds device_id, seeding every
    currently-registered device with a copy of that shared "wide" layout —
    since the pre-existing "default" device is the only one, it ends up
    right back where migration 001 first put it.
    """
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE widget_layout (widget_id TEXT PRIMARY KEY, layout TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO widget_layout (widget_id, layout) VALUES (?, ?)",
        [
            ("clock", '{"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}'),
            ("weather", '{"col": 2, "row": 1, "colSpan": 2, "rowSpan": 1}'),
        ],
    )
    conn.execute(
        "CREATE TABLE devices ("
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO devices (id, name, created_at, last_seen_at) VALUES "
        "('default', 'Original Device', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_layout("default", "default", "wide", "clock") == {
        "col": 1,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }
    assert db.get_widget_layout("default", "default", "wide", "weather") == {
        "col": 2,
        "row": 1,
        "colSpan": 2,
        "rowSpan": 1,
    }
    assert db.get_user("default") is None

    # Idempotent: re-running against an already-migrated DB doesn't error or duplicate data.
    db.init_db()
    assert db.list_widget_layouts("default", "default", "wide") == {
        "clock": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "weather": {"col": 2, "row": 1, "colSpan": 2, "rowSpan": 1},
    }


def test_migration_008_collapses_multiple_device_rows_into_a_single_wide_row(tmp_path, monkeypatch):
    """Simulates a pre-0.8 install with the old (user_id, device_id, widget_id)
    schema, where the same user saved layout from two different devices —
    exactly the shape that used to require the (buggy) copy-layout feature.
    Migration 008 collapses these into one row per (user_id, widget_id) under
    breakpoint "wide"; migration 009 then re-expands that shared "wide" row
    across every currently-registered device (both "phone" and "tablet" here,
    since both already have session/layout history), landing back at a
    per-device row rather than staying collapsed.
    """
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE widget_layout (
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            widget_id TEXT NOT NULL,
            layout TEXT NOT NULL,
            PRIMARY KEY (user_id, device_id, widget_id)
        )
        """
    )
    conn.executemany(
        "INSERT INTO widget_layout (user_id, device_id, widget_id, layout) VALUES (?, ?, ?, ?)",
        [
            ("alice", "phone", "clock", '{"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}'),
            ("alice", "tablet", "clock", '{"col": 3, "row": 3, "colSpan": 2, "rowSpan": 2}'),
        ],
    )
    conn.execute(
        "CREATE TABLE devices ("
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL"
        ")"
    )
    conn.executemany(
        "INSERT INTO devices (id, name, created_at, last_seen_at) "
        "VALUES (?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
        [("phone", "Phone"), ("tablet", "Tablet")],
    )
    # Already at the post-001 shape (user_id, device_id, widget_id) — skip
    # migration 001, which expects the older widget_id-only table, straight
    # to exercising migration 008/009 against this fixture.
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    # Both devices end up seeded with the same post-008 "wide" layout —
    # neither is silently dropped, and "narrow" stays unset for either.
    for device_id in ("phone", "tablet"):
        layouts = db.list_widget_layouts("alice", device_id, "wide")
        assert layouts.keys() == {"clock"}
        assert db.get_widget_layout("alice", device_id, "narrow", "clock") is None
