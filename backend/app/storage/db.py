"""SQLite persistence for AI widget run history.

A plain, unpooled sqlite3 connection is enough here: writes happen only
when a scheduled AI job finishes (at most a handful of times a day per
widget), and reads are single-row lookups for a dashboard polled by one
device.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    ran_at TEXT NOT NULL,
    result TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_runs_widget_id ON ai_runs (widget_id, ran_at DESC);

CREATE TABLE IF NOT EXISTS widget_settings (
    widget_id TEXT PRIMARY KEY,
    settings TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS widget_layout (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    layout TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id, widget_id)
);
CREATE INDEX IF NOT EXISTS idx_widget_layout_widget_id ON widget_layout (widget_id);

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
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL lets reads (the common case here) proceed without waiting on a
    # writer, and NORMAL sync skips an fsync per commit — on the slow SD-card
    # storage a Raspberry Pi typically boots from, that's the difference
    # between a write stalling the event loop for milliseconds vs tens of
    # milliseconds. Safe here since a lost "last commit" on power loss just
    # means re-fetching from the source on next refresh, not data corruption.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# Schema changes to a table _SCHEMA already created (adding/renaming a
# column, backfilling data) — `CREATE TABLE IF NOT EXISTS` alone only
# handles brand-new tables, not evolving an existing one on an upgrade.
# Append new SQL scripts here in order; each one is a single version step
# applied at most once, tracked via SQLite's built-in `PRAGMA user_version`.

# `widget_layout` gained a (user_id, device_id) dimension for multi-user/
# multi-device support. SQLite can't ALTER a PRIMARY KEY, so this rebuilds
# the table under a temp name and swaps it in. Existing rows (from a
# single-user, single-device install) are re-keyed under a "default"
# user/device id rather than dropped, so an upgrade preserves the live
# dashboard's current layout instead of resetting it. No FK constraints
# anywhere in this schema, so re-keying to an id that may not (yet, or ever)
# have a matching users/devices row is safe — it just means those rows are
# inert until/unless something creates that id. Explicit BEGIN/COMMIT
# because `_apply_migrations` only advances `PRAGMA user_version` after this
# whole script returns — without a transaction, a crash between DROP TABLE
# and the RENAME could lose the table on a retried boot.
_MIGRATION_001_USERS_DEVICES = """
BEGIN;

CREATE TABLE IF NOT EXISTS widget_layout_new (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    layout TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id, widget_id)
);

INSERT INTO widget_layout_new (user_id, device_id, widget_id, layout)
SELECT 'default', 'default', widget_id, layout FROM widget_layout;

DROP TABLE widget_layout;
ALTER TABLE widget_layout_new RENAME TO widget_layout;
CREATE INDEX IF NOT EXISTS idx_widget_layout_widget_id ON widget_layout (widget_id);

COMMIT;
"""


# Added the `role` column (for admin/member permissions) after `users` had
# already shipped, so unlike migration 001 this can't be folded into
# `_SCHEMA`'s `CREATE TABLE IF NOT EXISTS` — that only handles brand-new
# tables, not a column an already-created table is missing. Needs
# conditional logic a raw SQL script can't express (check column existence,
# count admins), so `_MIGRATIONS`/`_apply_migrations` accept a callable here
# instead of a SQL string. On a fresh install `users` is empty, so this is a
# no-op past adding the column — the resulting zero-admin, zero-user state
# is exactly what should trigger first-run onboarding. On an upgrade with
# existing profiles, promoting the oldest one keeps everyone's access
# working with no manual step.
def _migration_002_user_roles(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "role" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'member'")

    admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    if admin_count == 0:
        oldest = conn.execute("SELECT id FROM users ORDER BY created_at ASC LIMIT 1").fetchone()
        if oldest is not None:
            conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (oldest["id"],))


_MIGRATIONS: tuple[str | Callable[[sqlite3.Connection], None], ...] = (
    _MIGRATION_001_USERS_DEVICES,
    _migration_002_user_roles,
)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    for migration in _MIGRATIONS[current_version:]:
        if callable(migration):
            migration(conn)
        else:
            conn.executescript(migration)
    conn.execute(f"PRAGMA user_version = {len(_MIGRATIONS)}")


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _apply_migrations(conn)


def record_ai_run(widget_id: str, result: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO ai_runs (widget_id, ran_at, result) VALUES (?, ?, ?)",
            (widget_id, datetime.now(UTC).isoformat(), json.dumps(result)),
        )


def latest_ai_run(widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT ran_at, result FROM ai_runs WHERE widget_id = ? ORDER BY ran_at DESC LIMIT 1",
            (widget_id,),
        ).fetchone()
    if row is None:
        return None
    return {"ran_at": row["ran_at"], **json.loads(row["result"])}


def ai_run_history(widget_id: str, limit: int = 10) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ran_at, result FROM ai_runs WHERE widget_id = ? ORDER BY ran_at DESC LIMIT ?",
            (widget_id, limit),
        ).fetchall()
    return [{"ran_at": row["ran_at"], **json.loads(row["result"])} for row in rows]


def save_widget_settings(widget_id: str, settings: dict[str, Any]) -> None:
    """Persist a widget's full settings dict, overwriting any prior override.

    Lets settings changed at runtime (e.g. the weather widget's city) survive
    a backend restart without editing dashboard.yaml.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?) "
            "ON CONFLICT (widget_id) DO UPDATE SET settings = excluded.settings",
            (widget_id, json.dumps(settings)),
        )


def get_widget_settings(widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT settings FROM widget_settings WHERE widget_id = ?", (widget_id,)).fetchone()
    return None if row is None else json.loads(row["settings"])


def save_widget_layout(user_id: str, device_id: str, widget_id: str, layout: dict[str, Any]) -> None:
    """Persist a widget's grid position for a given (user, device), overwriting any prior override.

    Lets drag-to-rearrange edits made from the dashboard survive a backend
    restart without editing dashboard.yaml, the same way `save_widget_settings`
    does for runtime settings changes. Scoped per (user, device) so each
    household member can arrange each of their screens independently.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO widget_layout (user_id, device_id, widget_id, layout) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, device_id, widget_id) DO UPDATE SET layout = excluded.layout",
            (user_id, device_id, widget_id, json.dumps(layout)),
        )


def get_widget_layout(user_id: str, device_id: str, widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT layout FROM widget_layout WHERE user_id = ? AND device_id = ? AND widget_id = ?",
            (user_id, device_id, widget_id),
        ).fetchone()
    return None if row is None else json.loads(row["layout"])


def delete_widget_layout_for_widget(widget_id: str) -> None:
    """Drop every (user, device) layout override for a widget that's been removed."""
    with _connect() as conn:
        conn.execute("DELETE FROM widget_layout WHERE widget_id = ?", (widget_id,))


def list_widget_layouts(user_id: str, device_id: str) -> dict[str, dict[str, Any]]:
    """All layout overrides for a (user, device), keyed by widget_id.

    One query for the whole dashboard list rather than one per widget.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT widget_id, layout FROM widget_layout WHERE user_id = ? AND device_id = ?",
            (user_id, device_id),
        ).fetchall()
    return {row["widget_id"]: json.loads(row["layout"]) for row in rows}


def begin_photo_index_scan(widget_id: str) -> int:
    """Mints a new generation tag for a background photo-index scan of
    widget_id. Every chunk upserted during this scan must use this
    generation so `finish_photo_index_scan` can identify (and delete) rows
    left over from a previous scan.

    Uses the monotonic clock at nanosecond resolution rather than
    millisecond-truncated wall-clock time — two scans of a small photo
    source can legitimately complete within the same millisecond (more so
    now that WAL mode makes each write faster), and a collision here would
    make `finish_photo_index_scan` treat the newer scan's own rows as
    leftovers from the older one, deleting nothing stale.
    """
    return time.monotonic_ns()


def upsert_photo_index_chunk(widget_id: str, generation: int, photo_ids: list[str], start_position: int) -> None:
    """Upserts one chunk of photo_ids (already in enumeration order) for an
    in-progress scan. Safe to call multiple times per scan — each call is
    its own committed transaction, so a concurrent reader only ever sees a
    growing superset of the previous good index, never a truncated one.
    """
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO photo_index (widget_id, photo_id, position, generation) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (widget_id, photo_id) DO UPDATE SET "
            "position = excluded.position, generation = excluded.generation",
            [(widget_id, photo_id, start_position + offset, generation) for offset, photo_id in enumerate(photo_ids)],
        )


def finish_photo_index_scan(widget_id: str, generation: int) -> None:
    """Drops any photo_index row for widget_id not written by `generation`
    (i.e. photos removed from the source since the last scan), then marks
    the scan as successful.
    """
    with _connect() as conn:
        conn.execute(
            "DELETE FROM photo_index WHERE widget_id = ? AND generation != ?",
            (widget_id, generation),
        )
        conn.execute(
            "INSERT INTO photo_index_meta (widget_id, generation, updated_at, status, last_error) "
            "VALUES (?, ?, ?, 'ok', NULL) "
            "ON CONFLICT (widget_id) DO UPDATE SET generation = excluded.generation, "
            "updated_at = excluded.updated_at, status = 'ok', last_error = NULL",
            (widget_id, generation, datetime.now(UTC).isoformat()),
        )


def mark_photo_index_scan_failed(widget_id: str, error: str) -> None:
    """Records a failed scan without touching photo_index rows, so the
    previous good index (if any) keeps serving reads.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO photo_index_meta (widget_id, generation, updated_at, status, last_error) "
            "VALUES (?, 0, ?, 'error', ?) "
            "ON CONFLICT (widget_id) DO UPDATE SET updated_at = excluded.updated_at, "
            "status = 'error', last_error = excluded.last_error",
            (widget_id, datetime.now(UTC).isoformat(), error),
        )


def photo_index_photo_ids(widget_id: str) -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT photo_id FROM photo_index WHERE widget_id = ? ORDER BY position ASC",
            (widget_id,),
        ).fetchall()
    return [row["photo_id"] for row in rows]


def photo_index_status(widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT widget_id, generation, updated_at, status, last_error FROM photo_index_meta WHERE widget_id = ?",
            (widget_id,),
        ).fetchone()
    return None if row is None else dict(row)


def delete_photo_index(widget_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM photo_index WHERE widget_id = ?", (widget_id,))
        conn.execute("DELETE FROM photo_index_meta WHERE widget_id = ?", (widget_id,))


def get_app_settings() -> dict[str, str]:
    """Runtime overrides for global app config (AI provider keys, timezone, ...).

    Layered on top of the `.env`-backed `Settings` defaults, the same way
    `get_widget_settings` overrides `dashboard.yaml` — see
    `app.config.effective_settings`.
    """
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def create_alert(widget_id: str, message: str, severity: str, expires_in_minutes: int | None = None) -> dict[str, Any]:
    created_at = datetime.now(UTC)
    expires_at = (
        (created_at + timedelta(minutes=expires_in_minutes)).isoformat() if expires_in_minutes is not None else None
    )
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO alerts (widget_id, severity, message, created_at, expires_at, dismissed) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (widget_id, severity, message, created_at.isoformat(), expires_at),
        )
        alert_id = cursor.lastrowid
    return {
        "id": alert_id,
        "widget_id": widget_id,
        "severity": severity,
        "message": message,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at,
        "dismissed": False,
    }


def list_active_alerts(widget_id: str) -> list[dict[str, Any]]:
    """Alerts for `widget_id` that haven't been dismissed or expired, newest first."""
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, widget_id, severity, message, created_at, expires_at, dismissed FROM alerts "
            "WHERE widget_id = ? AND dismissed = 0 AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY created_at DESC",
            (widget_id, now),
        ).fetchall()
    return [dict(row) | {"dismissed": bool(row["dismissed"])} for row in rows]


def get_alert(alert_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, widget_id, severity, message, created_at, expires_at, dismissed FROM alerts WHERE id = ?",
            (alert_id,),
        ).fetchone()
    return None if row is None else dict(row) | {"dismissed": bool(row["dismissed"])}


def dismiss_alert(alert_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE alerts SET dismissed = 1 WHERE id = ?", (alert_id,))


def save_oauth_tokens(
    provider: str, refresh_token: str, access_token: str | None = None, expires_at: str | None = None
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO oauth_tokens (provider, refresh_token, access_token, expires_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (provider) DO UPDATE SET "
            "refresh_token = excluded.refresh_token, access_token = excluded.access_token, "
            "expires_at = excluded.expires_at",
            (provider, refresh_token, access_token, expires_at),
        )


def get_oauth_tokens(provider: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT provider, refresh_token, access_token, expires_at FROM oauth_tokens WHERE provider = ?",
            (provider,),
        ).fetchone()
    return None if row is None else dict(row)


def save_oauth_access_token(provider: str, access_token: str, expires_at: str) -> None:
    """Update the cached access token for a provider whose refresh token is already stored."""
    with _connect() as conn:
        conn.execute(
            "UPDATE oauth_tokens SET access_token = ?, expires_at = ? WHERE provider = ?",
            (access_token, expires_at, provider),
        )


def save_custom_widget(widget_id: str, type_: str, layout: dict[str, Any], tab: str | None) -> None:
    """Persist a widget added via the UI (no dashboard.yaml entry to live in)."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO custom_widgets (id, type, layout, tab) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET type = excluded.type, layout = excluded.layout, "
            "tab = excluded.tab",
            (widget_id, type_, json.dumps(layout), tab),
        )


def delete_custom_widget(widget_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM custom_widgets WHERE id = ?", (widget_id,))


def list_custom_widgets() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, type, layout, tab FROM custom_widgets").fetchall()
    return [
        {"id": row["id"], "type": row["type"], "layout": json.loads(row["layout"]), "tab": row["tab"]} for row in rows
    ]


def mark_widget_removed(widget_id: str) -> None:
    """Soft-delete a dashboard.yaml-defined widget — the file itself is left alone."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO removed_widget_ids (widget_id) VALUES (?) ON CONFLICT (widget_id) DO NOTHING",
            (widget_id,),
        )


def removed_widget_ids() -> set[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT widget_id FROM removed_widget_ids").fetchall()
    return {row["widget_id"] for row in rows}


def save_app_settings(overrides: dict[str, str | None]) -> None:
    """Upsert app setting overrides; a `None` value clears that key."""
    with _connect() as conn:
        for key, value in overrides.items():
            if value is None:
                conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            else:
                conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )


# --- Users, devices, sessions, preferences -------------------------------
#
# No FK constraints here, matching the rest of this schema (no table in
# `_SCHEMA` uses one, and `_connect()` never sets `PRAGMA foreign_keys=ON`).
# Cascades on delete are done by hand below, the same hand-rolled style as
# everything else in this module.


def create_user(
    id: str,
    name: str,
    avatar: str | None,
    pin_hash: str | None,
    pin_salt: str | None,
    pin_iterations: int | None,
    created_at: str,
    role: str = "member",
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at, role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (id, name, avatar, pin_hash, pin_salt, pin_iterations, created_at, role),
        )


def get_user(user_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return None if row is None else dict(row)


def list_users() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
    return [dict(row) for row in rows]


def update_user(user_id: str, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    with _connect() as conn:
        conn.execute(f"UPDATE users SET {columns} WHERE id = ?", (*fields.values(), user_id))


def delete_user(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM widget_layout WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def create_device(id: str, name: str, created_at: str, last_seen_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO devices (id, name, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
            (id, name, created_at, last_seen_at),
        )


def get_device(device_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    return None if row is None else dict(row)


def list_devices() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY created_at ASC").fetchall()
    return [dict(row) for row in rows]


def update_device(device_id: str, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    with _connect() as conn:
        conn.execute(f"UPDATE devices SET {columns} WHERE id = ?", (*fields.values(), device_id))


def touch_device(device_id: str, last_seen_at: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE devices SET last_seen_at = ? WHERE id = ?", (last_seen_at, device_id))


def delete_device(device_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE device_id = ?", (device_id,))
        conn.execute("DELETE FROM widget_layout WHERE device_id = ?", (device_id,))
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))


def create_session(id: str, user_id: str, device_id: str, created_at: str, expires_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, device_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (id, user_id, device_id, created_at, expires_at),
        )


def get_session(session_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return None if row is None else dict(row)


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def delete_sessions_for_user(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def delete_sessions_for_device(device_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE device_id = ?", (device_id,))


def delete_expired_sessions(now: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))


_DEFAULT_PREFERENCES: dict[str, Any] = {"theme": "dark"}


def get_user_preferences(user_id: str) -> dict[str, Any]:
    with _connect() as conn:
        row = conn.execute("SELECT preferences FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    overrides = json.loads(row["preferences"]) if row else {}
    return {**_DEFAULT_PREFERENCES, **overrides}


def save_user_preferences(user_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge `overrides` onto the user's stored preferences and persist the result."""
    merged = {**get_user_preferences(user_id), **overrides}
    with _connect() as conn:
        conn.execute(
            "INSERT INTO user_preferences (user_id, preferences) VALUES (?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET preferences = excluded.preferences",
            (user_id, json.dumps(merged)),
        )
    return merged
