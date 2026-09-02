from __future__ import annotations

import sqlite3

import pytest

from app.storage import db


def test_connect_closes_connection_on_clean_exit(tmp_db):
    with db._connect() as conn:
        pass

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_connect_closes_connection_on_exception(tmp_db):
    conn_holder = []
    with pytest.raises(ValueError):
        with db._connect() as conn:
            conn_holder.append(conn)
            raise ValueError("boom")

    with pytest.raises(sqlite3.ProgrammingError):
        conn_holder[0].execute("SELECT 1")


def test_connect_rolls_back_on_exception(tmp_db):
    with pytest.raises(ValueError):
        with db._connect() as conn:
            conn.execute(
                "INSERT INTO ai_runs (widget_id, ran_at, result) VALUES (?, ?, ?)",
                ("widget", "2026-01-01T00:00:00", "{}"),
            )
            raise ValueError("boom")

    with db._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ai_runs").fetchone()[0] == 0


def test_ping_succeeds_against_a_healthy_db(tmp_db):
    db.ping()  # should not raise
