from __future__ import annotations

import sqlite3

from app.storage import db


def test_get_widget_layout_returns_none_when_unset(tmp_db):
    assert db.get_widget_layout("alice", "dev1", "clock") is None


def test_save_then_get_widget_layout_round_trips(tmp_db):
    db.save_widget_layout("alice", "dev1", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})

    assert db.get_widget_layout("alice", "dev1", "clock") == {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}


def test_save_widget_layout_overwrites_prior_value_for_same_user_and_device(tmp_db):
    db.save_widget_layout("alice", "dev1", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "dev1", "clock", {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1})

    assert db.get_widget_layout("alice", "dev1", "clock") == {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1}


def test_widget_layout_is_independent_per_device_for_same_user(tmp_db):
    db.save_widget_layout("alice", "phone", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "tablet", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "phone", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("alice", "tablet", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_widget_layout_is_independent_per_user_for_same_device(tmp_db):
    db.save_widget_layout("alice", "tablet", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("bob", "tablet", "clock", {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2})

    assert db.get_widget_layout("alice", "tablet", "clock") == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert db.get_widget_layout("bob", "tablet", "clock") == {"col": 5, "row": 5, "colSpan": 2, "rowSpan": 2}


def test_list_widget_layouts_returns_all_overrides_for_a_user_and_device(tmp_db):
    db.save_widget_layout("alice", "tablet", "clock", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("alice", "tablet", "weather", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    db.save_widget_layout("bob", "tablet", "clock", {"col": 9, "row": 9, "colSpan": 1, "rowSpan": 1})

    layouts = db.list_widget_layouts("alice", "tablet")

    assert layouts == {
        "clock": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "weather": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1},
    }


def test_migration_reseats_pre_existing_single_user_layout_under_default_user_and_device(tmp_path, monkeypatch):
    """Simulates upgrading a pre-multi-user install: an old-shape `widget_layout`
    table (widget_id PRIMARY KEY, no user_id/device_id) already has live rows
    before `init_db()` ever runs the new schema/migration against this file.

    Migration 001 re-keys these rows under a "default" user/device id but (as
    of the role migration) no longer creates matching `users`/`devices` rows
    itself — that's onboarding's job now, and onboarding mints a random id,
    not "default". No FK constraints means this doesn't error; it just means
    the re-keyed rows are inert unless something later creates a "default"
    id, which is an accepted trade-off for a very old, pre-multi-user DB.
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

    assert db.get_widget_layout("default", "default", "clock") == {
        "col": 1,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }
    assert db.get_widget_layout("default", "default", "weather") == {
        "col": 2,
        "row": 1,
        "colSpan": 2,
        "rowSpan": 1,
    }
    assert db.get_user("default") is None
    assert db.get_device("default") is None

    # Idempotent: re-running against an already-migrated DB doesn't error or duplicate data.
    db.init_db()
    assert db.list_widget_layouts("default", "default") == {
        "clock": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        "weather": {"col": 2, "row": 1, "colSpan": 2, "rowSpan": 1},
    }
