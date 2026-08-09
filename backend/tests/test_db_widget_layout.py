from __future__ import annotations

import sqlite3

from app.storage import db


def test_get_widget_layout_returns_none_when_unset(tmp_db):
    assert db.get_widget_layout("alice", "wide", "clock") is None


def test_save_then_get_widget_layout_round_trips(tmp_db):
    db.save_widget_layout("alice", "wide", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})

    assert db.get_widget_layout("alice", "wide", "clock") == {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}


def test_save_widget_layout_overwrites_prior_value_for_same_user_and_breakpoint(tmp_db):
    db.save_widget_layout("alice", "wide", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "wide", "clock", {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1})

    assert db.get_widget_layout("alice", "wide", "clock") == {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1}


def test_widget_layout_is_independent_per_breakpoint_for_same_user(tmp_db):
    db.save_widget_layout("alice", "narrow", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "wide", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "narrow", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("alice", "wide", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_widget_layout_is_independent_per_user_for_same_breakpoint(tmp_db):
    db.save_widget_layout("alice", "wide", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("bob", "wide", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "wide", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("bob", "wide", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_list_widget_layouts_returns_all_overrides_for_a_user_and_breakpoint(tmp_db):
    db.save_widget_layout("alice", "wide", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "wide", "weather", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("bob", "wide", "clock", {"col": 9, "row": 9, "colSpan": 1, "rowSpan": 1})

    layouts = db.list_widget_layouts("alice", "wide")

    assert layouts == {
        "clock": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "weather": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1},
    }


def test_migration_reseats_pre_existing_single_user_layout_under_default_user_and_wide_breakpoint(
    tmp_path, monkeypatch
):
    """Simulates upgrading a pre-multi-user install: an old-shape `widget_layout`
    table (widget_id PRIMARY KEY, no user_id/device_id) already has live rows
    before `init_db()` ever runs the new schema/migrations against this file.

    Migration 001 re-keys these rows under a "default" user/device id (no
    matching `users`/`devices` rows — that's onboarding's job, and onboarding
    mints a random id, not "default"). Migration 008 then re-keys layout again,
    collapsing device_id into breakpoint, landing everything under "wide" since
    that's the primary layout concept the app was built around. No FK
    constraints means this doesn't error; it just means the re-keyed rows are
    inert unless something later creates a "default" user id.
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
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    assert db.get_widget_layout("default", "wide", "clock") == {
        "col": 1,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }
    assert db.get_widget_layout("default", "wide", "weather") == {
        "col": 2,
        "row": 1,
        "colSpan": 2,
        "rowSpan": 1,
    }
    assert db.get_user("default") is None
    assert db.get_device("default") is None

    # Idempotent: re-running against an already-migrated DB doesn't error or duplicate data.
    db.init_db()
    assert db.list_widget_layouts("default", "wide") == {
        "clock": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "weather": {"col": 2, "row": 1, "colSpan": 2, "rowSpan": 1},
    }


def test_migration_008_collapses_multiple_device_rows_into_a_single_wide_row(tmp_path, monkeypatch):
    """Simulates a pre-0.8 install with the old (user_id, device_id, widget_id)
    schema, where the same user saved layout from two different devices —
    exactly the shape that used to require the (buggy) copy-layout feature.
    Migration 008 must collapse these into one row per (user_id, widget_id)
    under breakpoint "wide" without hitting a primary-key collision.
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
    # Already at the post-001 shape (user_id, device_id, widget_id) — skip
    # migration 001, which expects the older widget_id-only table, straight
    # to exercising migration 008 against this fixture.
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    layouts = db.list_widget_layouts("alice", "wide")
    assert layouts.keys() == {"clock"}
    assert db.get_widget_layout("alice", "narrow", "clock") is None
