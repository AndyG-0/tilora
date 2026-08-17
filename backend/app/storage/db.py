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

from app.config import DB_PATH, SECRET_APP_SETTINGS_KEYS
from app.crypto import decrypt, encrypt

_SCHEMA = """
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

-- User-set override of a widget instance's display name, used to tell
-- apart multiple instances of the same tile type (e.g. two Weather tiles)
-- in places like the AI insights topic list. Keyed by widget_id rather than
-- living on custom_widgets so it also covers dashboard.yaml-defined widgets
-- that never get a custom_widgets row (e.g. the Docker/Podman pair, both
-- type "container"). Row absent means no override — see
-- app.plugins.naming.display_names for the auto-generated fallback.
CREATE TABLE IF NOT EXISTS widget_custom_names (
    widget_id TEXT PRIMARY KEY,
    custom_name TEXT NOT NULL
);

-- One row per physical LAN device (Pi-hole, Jellyfin, Synology, Asus
-- Router, HDHomeRun, and each named Docker/Podman host) shared across every
-- widget instance of that type/host, instead of duplicating connection
-- settings (host/port/credentials) per widget_id the way widget_settings
-- does. Singleton integration types use `id = type` (a direct primary-key
-- lookup, since there's only ever one row); Container is the one
-- multi-instance type, using a generated id, with each Container widget's
-- own widget_settings row carrying a `network_integration_id` reference to
-- pick which row it uses. See app.plugins.network_settings. `settings` is a
-- JSON blob with `password`/`api_key` values Fernet-encrypted per-key (same
-- mechanism as app_settings, see app.crypto), not the whole column.
CREATE TABLE IF NOT EXISTS network_integrations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    settings TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_network_integrations_type ON network_integrations (type);

-- Keyed by (user, device, breakpoint): tile position/size is a "device
-- settings" concern (see CONTRIBUTING.md's settings-tiers section) scoped to
-- the specific household member using the specific physical screen, so two
-- people sharing a screen — or one person's two screens — never see or
-- clobber each other's arrangement. See migration 008 for the breakpoint-only
-- keying this replaced (that was the direct cause of tiles from one device
-- "leaking" onto another) and migration 009 for how device_id came back.
CREATE TABLE IF NOT EXISTS widget_layout (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    breakpoint TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    layout TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id, breakpoint, widget_id)
);
CREATE INDEX IF NOT EXISTS idx_widget_layout_widget_id ON widget_layout (widget_id);

-- Per-(user, device) screensaver configuration (enabled, idle timeout,
-- rotation interval, which widgets to cycle through) — same scoping as
-- widget_layout above, since each household member's idle-screensaver
-- behavior can differ per physical screen they use. One row per pair, not
-- one per widget, so unlike widget_layout there's no widget_id column or
-- per-widget index: the widget id list lives inside the settings blob.
CREATE TABLE IF NOT EXISTS screensaver_settings (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    settings TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id)
);

-- Per-user overrides for "personal"-scope plugins (e.g. RSS, calendar) whose
-- content should differ per household member, unlike the shared/global
-- widget_settings table above which backs "network"-scope plugins (NAS,
-- router, ...) that are the same for the whole household. See
-- app.plugins.base.Plugin.settings_scope.
CREATE TABLE IF NOT EXISTS widget_user_settings (
    user_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    settings TEXT NOT NULL,
    PRIMARY KEY (user_id, widget_id)
);
CREATE INDEX IF NOT EXISTS idx_widget_user_settings_widget_id ON widget_user_settings (widget_id);

-- Per-device overrides for individual settings keys a plugin marks via
-- Plugin.device_overridable_settings — orthogonal to settings_scope above:
-- a "network"-scope plugin's shared settings still need an admin to change,
-- but a specific field (e.g. Jellyfin's playback_mode) can still be tuned
-- per physical device by any user, since it doesn't touch shared config.
-- Layered on top of the network/personal value, not a replacement for it —
-- an unset device falls back to whatever settings_scope already resolved.
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

-- owner_user_id/owner_device_id are NULL for a widget added before ownership
-- tracking existed (migration 010) — grandfathered as visible to everyone,
-- same as a dashboard.yaml widget, since there's no historical owner to
-- recover and no previously-visible tile should disappear on upgrade. A
-- widget added via the UI after that migration always has both set together:
-- it's private to the (user, device) pair that created it until deleted, per
-- the "widget settings" visibility rules in app.api.widgets.
CREATE TABLE IF NOT EXISTS custom_widgets (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    layout TEXT NOT NULL,
    tab TEXT,
    owner_user_id TEXT,
    owner_device_id TEXT
);

-- Superseded by hidden_widget_ids below (migration 011 seeds it from this
-- table's contents) — left in place, unread by any code, as a harmless
-- escape hatch rather than dropped outright.
CREATE TABLE IF NOT EXISTS removed_widget_ids (
    widget_id TEXT PRIMARY KEY
);

-- A shared default tile (dashboard.yaml, or a legacy pre-ownership custom
-- widget) hidden from just this (user, device) pair's own widget list —
-- not a delete, since the tile still belongs to/is visible for everyone
-- else. Any logged-in user may hide one for their own screen; this is
-- intentionally not admin-gated (decluttering your own dashboard isn't a
-- shared-state change). See app.api.widgets for how this and
-- owner_user_id/owner_device_id above combine into the visibility rules.
CREATE TABLE IF NOT EXISTS hidden_widget_ids (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id, widget_id)
);

-- `user_id` distinguishes whose library this row belongs to: '' (the
-- default) for a widget-wide shared index (local/icloud_shared/immich, one
-- library for the whole household), or an actual user id for icloud_private,
-- where each connected household member has their own Apple ID and thus
-- their own private library — see app.plugins.photos.indexer and
-- PhotosPlugin._photo_index_user_id. Without this dimension, two users
-- sharing one icloud_private widget clobbered each other's scan results.
CREATE TABLE IF NOT EXISTS photo_index (
    widget_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    photo_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    generation INTEGER NOT NULL,
    PRIMARY KEY (widget_id, user_id, photo_id)
);
-- Not indexed here: on an upgrade this CREATE TABLE is a no-op against the
-- pre-existing (pre-`user_id`) table, so an index referencing `user_id`
-- would fail before migration 014 gets a chance to add the column.
-- Migration 014 creates this same index itself, after rebuilding the table.

CREATE TABLE IF NOT EXISTS photo_index_meta (
    widget_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    generation INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    last_error TEXT,
    PRIMARY KEY (widget_id, user_id)
);

-- Dedup for the severe-weather scheduler job: tracks which NWS alert (or
-- synthesized forecast-heuristic) keys have already been turned into an
-- `alerts` row for a given weather widget, so a 15-minute poll doesn't
-- re-alert on the same ongoing warning. No expiry/cleanup — same
-- unbounded-growth tradeoff as the alerts table itself.
CREATE TABLE IF NOT EXISTS severe_weather_seen (
    widget_id TEXT NOT NULL,
    alert_key TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (widget_id, alert_key)
);

-- Deliberately per-user (user_id, added by migration 012 for an upgrade)
-- rather than shared household-wide: each member tracks their own
-- deliveries, the same "user-level settings" tier as Steam/Goodreads — see
-- app.plugins.packages.plugin's settings_scope comment.
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
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
-- idx_packages_widget_user is NOT created here: on an upgrade this CREATE
-- TABLE is a no-op against the pre-existing (pre-`user_id`) table, so an
-- index referencing `user_id` would fail before migration 012 gets a chance
-- to add the column. Migration 012 creates this same index itself, after
-- adding the column.

-- A household member's own RSS feed catalog, independent of any single
-- widget instance — feeds are added/removed here once, then any of that
-- same user's RSS tiles picks a subset via feed_ids in its (personal-scope)
-- widget settings. Deliberately per-user rather than shared across the
-- household: each member reads different headlines (see
-- app.plugins.rss.plugin's settings_scope comment).
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

-- Per-user third-party credentials (currently just iCloud) — the user-level
-- analogue of network_integrations above, which holds one shared credential
-- per physical LAN device for the whole household. `credentials` is a JSON
-- blob with any password-shaped value Fernet-encrypted per-key (same
-- mechanism as network_integrations/app_settings, see app.crypto). `provider`
-- lets one user hold more than one kind of credential (e.g. iCloud today,
-- something else later) without a new table per provider.
CREATE TABLE IF NOT EXISTS user_credentials (
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    credentials TEXT NOT NULL,
    PRIMARY KEY (user_id, provider)
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


def _upsert(conn: sqlite3.Connection, table: str, row: dict[str, Any], key_columns: tuple[str, ...]) -> None:
    """`INSERT INTO table (...) VALUES (...) ON CONFLICT (key_columns) DO
    UPDATE SET ...` for `row`, generically — the same shape hand-copied
    across every settings/preferences table below (widget_settings,
    widget_layout, widget_user_settings, widget_device_settings,
    screensaver_settings, user_preferences, oauth_tokens, custom_widgets,
    app_settings) before this helper existed. `table` and `key_columns` are
    always caller-supplied literals (never request data), so building SQL
    via f-string here carries no injection risk.
    """
    columns = list(row.keys())
    update_columns = [c for c in columns if c not in key_columns]
    conflict_action = (
        "DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in update_columns) if update_columns else "DO NOTHING"
    )
    conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
        f"ON CONFLICT ({', '.join(key_columns)}) {conflict_action}",
        [row[c] for c in columns],
    )


# Schema changes to a table _SCHEMA already created (adding/renaming a
# column, backfilling data) — `CREATE TABLE IF NOT EXISTS` alone only
# handles brand-new tables, not evolving an existing one on an upgrade.
# Append new SQL scripts here in order; each one is a single version step,
# applied at most once and committed atomically (together with its own
# `PRAGMA user_version` bump) by `_apply_migrations` — see that function for
# why script migrations don't need their own BEGIN/COMMIT.

# `widget_layout` gained a (user_id, device_id) dimension for multi-user/
# multi-device support. SQLite can't ALTER a PRIMARY KEY, so this rebuilds
# the table under a temp name and swaps it in. Existing rows (from a
# single-user, single-device install) are re-keyed under a "default"
# user/device id rather than dropped, so an upgrade preserves the live
# dashboard's current layout instead of resetting it. No FK constraints
# anywhere in this schema, so re-keying to an id that may not (yet, or ever)
# have a matching users/devices row is safe — it just means those rows are
# inert until/unless something creates that id.
_MIGRATION_001_USERS_DEVICES = """
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


_PERSONAL_SCOPE_WIDGET_TYPES = ("rss", "calendar", "calendar_caldav", "calendar_microsoft")


# `rss`/`calendar` moved from global (whole-household) settings to per-user
# settings (see app.plugins.base.Plugin.settings_scope and the
# widget_user_settings table above) — this seeds every existing user with a
# copy of whatever was previously the one shared value, so upgrading doesn't
# silently blank out anyone's feeds/calendar picks. Detects which
# widget_settings rows are personal-scope by widget_id convention: a
# dashboard.yaml-sourced widget keeps the plugin's own id (e.g. "rss"), a
# UI-added one has a generated id whose type is recorded in custom_widgets.
# The original widget_settings row is left in place — nothing reads it for
# these types anymore, but keeping it costs nothing and is an escape hatch if
# this id-based detection ever misses a dashboard.yaml entry with a
# non-default `id:` override.
def _migration_003_seed_personal_widget_settings(conn: sqlite3.Connection) -> None:
    custom_types = {row["id"]: row["type"] for row in conn.execute("SELECT id, type FROM custom_widgets")}
    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users")]
    if not user_ids:
        return

    for row in conn.execute("SELECT widget_id, settings FROM widget_settings").fetchall():
        widget_id = row["widget_id"]
        widget_type = custom_types.get(widget_id, widget_id)
        if widget_type not in _PERSONAL_SCOPE_WIDGET_TYPES:
            continue
        conn.executemany(
            "INSERT INTO widget_user_settings (user_id, widget_id, settings) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, widget_id) DO NOTHING",
            [(user_id, widget_id, row["settings"]) for user_id in user_ids],
        )


# The `docker` and `podman` plugins were merged into a single `container`
# plugin with an `engine` setting ("docker" | "podman"). dashboard.yaml-
# sourced widgets need no migration: `main.py:load_plugins` merges settings
# as `{**plugin_cls.default_settings, **yaml_settings, **db_overrides}`, and
# the updated dashboard.yaml now supplies `engine` at the yaml layer, which
# any pre-existing `widget_settings` override (saved before `engine`
# existed) simply inherits since it never set that key. UI-added widgets
# have no yaml entry to inherit from, so their `custom_widgets.type` and
# `widget_settings` row are rewritten explicitly here instead.
def _migration_004_merge_container_widgets(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, type FROM custom_widgets WHERE type IN ('docker', 'podman')").fetchall()
    for row in rows:
        widget_id, engine = row["id"], row["type"]
        conn.execute("UPDATE custom_widgets SET type = 'container' WHERE id = ?", (widget_id,))
        existing = conn.execute("SELECT settings FROM widget_settings WHERE widget_id = ?", (widget_id,)).fetchone()
        settings = json.loads(existing["settings"]) if existing else {}
        settings.setdefault("engine", engine)
        conn.execute(
            "INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?) "
            "ON CONFLICT (widget_id) DO UPDATE SET settings = excluded.settings",
            (widget_id, json.dumps(settings)),
        )


_SPORTS_WEATHER_PERSONAL_SCOPE_WIDGET_TYPES = ("sports", "weather")


# `sports`/`weather` moved from global (whole-household) settings to per-user
# settings (favorite teams, home location) — same reasoning and mechanics as
# _migration_003_seed_personal_widget_settings above, just for a different
# widget-type list added later. See that migration's comment for the
# widget-id-to-type detection logic this mirrors.
def _migration_005_seed_personal_sports_weather_settings(conn: sqlite3.Connection) -> None:
    custom_types = {row["id"]: row["type"] for row in conn.execute("SELECT id, type FROM custom_widgets")}
    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users")]
    if not user_ids:
        return

    for row in conn.execute("SELECT widget_id, settings FROM widget_settings").fetchall():
        widget_id = row["widget_id"]
        widget_type = custom_types.get(widget_id, widget_id)
        if widget_type not in _SPORTS_WEATHER_PERSONAL_SCOPE_WIDGET_TYPES:
            continue
        conn.executemany(
            "INSERT INTO widget_user_settings (user_id, widget_id, settings) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, widget_id) DO NOTHING",
            [(user_id, widget_id, row["settings"]) for user_id in user_ids],
        )


# RSS feeds moved out of each tile's own settings into a per-user catalog
# (the `rss_feeds` table above) shared across that same user's RSS tiles —
# see app.plugins.rss.plugin. This seeds the catalog from every existing
# widget_user_settings row's inline `feeds: [{url, name}]` list (RSS has
# been personal-scope since migration 003, so that's the only place old
# feed lists can live) and rewrites the row to reference the new catalog
# entries by id instead, dropping the now-obsolete `feeds`/`item_limit`
# keys (item_limit moved onto each catalog feed, default 10). Detects a
# row's widget type the same way migrations 003/005 do. Safe to run only
# once per row: a row with no `feeds` key (fresh install, or already
# migrated) is skipped rather than re-processed.
def _migration_006_seed_rss_feed_catalog(conn: sqlite3.Connection) -> None:
    custom_types = {row["id"]: row["type"] for row in conn.execute("SELECT id, type FROM custom_widgets")}

    for row in conn.execute("SELECT user_id, widget_id, settings FROM widget_user_settings").fetchall():
        widget_type = custom_types.get(row["widget_id"], row["widget_id"])
        if widget_type != "rss":
            continue

        settings = json.loads(row["settings"])
        feeds = settings.get("feeds")
        if feeds is None:
            continue

        feed_ids = []
        for feed in feeds:
            url = feed.get("url")
            if not url:
                continue
            existing = conn.execute(
                "SELECT id FROM rss_feeds WHERE user_id = ? AND url = ?", (row["user_id"], url)
            ).fetchone()
            if existing is not None:
                feed_ids.append(existing["id"])
                continue
            cursor = conn.execute(
                "INSERT INTO rss_feeds (user_id, url, name, item_limit, created_at) VALUES (?, ?, ?, 10, ?)",
                (row["user_id"], url, feed.get("name"), datetime.now(UTC).isoformat()),
            )
            feed_ids.append(cursor.lastrowid)

        new_settings = {k: v for k, v in settings.items() if k not in ("feeds", "item_limit")}
        new_settings["feed_ids"] = feed_ids
        conn.execute(
            "UPDATE widget_user_settings SET settings = ? WHERE user_id = ? AND widget_id = ?",
            (json.dumps(new_settings), row["user_id"], row["widget_id"]),
        )


# Per-type primary connection field used to pick a winner when more than one
# widget of the same singleton network-integration type exists (today,
# dashboard.yaml has exactly one of each, so this is mostly a safety net):
# the first widget whose effective settings has this field non-empty wins,
# rather than an arbitrary first-seen one that might be an unconfigured stub.
_SINGLETON_PRIMARY_HOST_KEY = {
    "pihole": "host",
    "jellyfin": "host",
    "synology": "host",
    "asus_router": "host",
    "hdhomerun": "tuner_host",
}


# Connection settings (host, port, credentials) for the six LAN-device plugin
# types moved out of per-widget settings into a shared `network_integrations`
# row per physical device, edited once instead of per widget instance (see
# `app.plugins.network_settings`). dashboard.yaml still has these fields
# inline in each widget's `settings:` block at the time this runs (that file
# gets hand-edited separately, after this migration is verified against
# production data) — so, unlike migrations 003/005/006, this one has to read
# dashboard.yaml as well as the DB to find the real values to migrate,
# via the same `load_dashboard_config`/`list_widget_configs` merge
# `main.py:load_plugins` used to do before this refactor. Uses raw SQL
# against the migration's own `conn` throughout rather than the
# save_widget_settings/get_widget_settings/save_network_integration helpers,
# since those each open their own new connection via `_connect()`, which
# would contend with this function's own open migration transaction.
def _migration_007_extract_network_integrations(conn: sqlite3.Connection) -> None:
    from uuid import uuid4

    from app.config import DASHBOARD_CONFIG_PATH, load_dashboard_config
    from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE

    # dashboard.yaml is gitignored (a per-deployment file; docker-entrypoint.sh
    # seeds it from dashboard.example.yaml before the app starts) and doesn't
    # exist yet in a fresh checkout or the CI/test environment. Fall back to
    # no YAML-defined widgets rather than erroring.
    yaml_config = load_dashboard_config() if DASHBOARD_CONFIG_PATH.exists() else {"widgets": []}
    # Deliberately not `app.config.list_widget_configs`/`db.list_custom_widgets`
    # here: both now also select custom_widgets' owner_user_id/owner_device_id
    # columns, which don't exist yet at this point in a fresh-to-current
    # migration run (added later by migration 010) — and only `id`/`type`/
    # `settings` are needed below anyway. Queried via this migration's own
    # `conn` rather than a second `_connect()`'d connection, consistent with
    # the rest of this function.
    widgets = list(yaml_config.get("widgets", []))
    widgets += [
        {"id": row["id"], "type": row["type"], "settings": {}}
        for row in conn.execute("SELECT id, type FROM custom_widgets")
    ]

    def _db_overrides(widget_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT settings FROM widget_settings WHERE widget_id = ?", (widget_id,)).fetchone()
        return json.loads(row["settings"]) if row else {}

    def _save_widget_settings(widget_id: str, settings: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?) "
            "ON CONFLICT (widget_id) DO UPDATE SET settings = excluded.settings",
            (widget_id, json.dumps(settings)),
        )

    def _create_integration(id_: str, type_: str, name: str, settings: dict[str, Any]) -> None:
        stored = _encrypt_network_integration_settings(settings)
        conn.execute(
            "INSERT INTO network_integrations (id, type, name, settings) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (id) DO NOTHING",
            (id_, type_, name, json.dumps(stored)),
        )

    for type_, plugin_cls in PLUGIN_CLASSES_BY_TYPE.items():
        if not plugin_cls.network_integration_type or not plugin_cls.network_integration_singleton:
            continue
        integration_type = plugin_cls.network_integration_type
        if conn.execute("SELECT id FROM network_integrations WHERE id = ?", (integration_type,)).fetchone():
            continue  # already migrated (or seeded) — leave it alone

        connection_keys = set(plugin_cls.network_default_settings.keys())
        entries: list[tuple[str, dict[str, Any]]] = []
        for widget in widgets:
            if widget["type"] != type_:
                continue
            effective = {
                **plugin_cls.network_default_settings,
                **plugin_cls.default_settings,
                **widget.get("settings", {}),
                **_db_overrides(widget["id"]),
            }
            entries.append((widget["id"], effective))
        if not entries:
            continue  # no widget of this type exists yet — nothing to migrate

        primary_key = _SINGLETON_PRIMARY_HOST_KEY.get(integration_type)
        winner = next((e for _, e in entries if primary_key and e.get(primary_key)), entries[0][1])
        integration_settings = {k: winner.get(k, plugin_cls.network_default_settings[k]) for k in connection_keys}
        _create_integration(integration_type, integration_type, plugin_cls.name, integration_settings)

        for widget_id, _ in entries:
            overrides = _db_overrides(widget_id)
            if connection_keys & overrides.keys():
                _save_widget_settings(widget_id, {k: v for k, v in overrides.items() if k not in connection_keys})

    container_cls = PLUGIN_CLASSES_BY_TYPE.get("container")
    if container_cls is not None:
        connection_keys = set(container_cls.network_default_settings.keys())
        for widget in widgets:
            if widget["type"] != "container":
                continue
            widget_id = widget["id"]
            overrides = _db_overrides(widget_id)
            if "network_integration_id" in overrides:
                continue  # already migrated
            effective = {
                **container_cls.network_default_settings,
                **container_cls.default_settings,
                **widget.get("settings", {}),
                **overrides,
            }
            integration_settings = {
                k: effective.get(k, container_cls.network_default_settings[k]) for k in connection_keys
            }
            integration_id = f"container-{uuid4().hex[:8]}"
            _create_integration(integration_id, "container", widget_id, integration_settings)
            _save_widget_settings(widget_id, {"network_integration_id": integration_id})


# `widget_layout` moved from a (user_id, device_id) key to (user_id,
# breakpoint): a tile's position is now shared by every device that renders
# at the same viewport class (see the table comment above) instead of being
# re-established from scratch on every new physical device. SQLite can't
# ALTER a PRIMARY KEY, so this rebuilds the table under a temp name and swaps
# it in, same approach as migration 001.
#
# Multiple old device rows for the same (user_id, widget_id) would collide
# under the new key, so this collapses them: one survivor per
# (user_id, widget_id), picked deterministically via MAX(rowid), landing
# under the 'wide' breakpoint. There's no signal anywhere in the old schema
# for which device was wide vs. narrow, and 'wide' (the original 4-column
# kiosk grid) is this app's primary layout concept, so defaulting there
# preserves the live dashboard's arrangement across the upgrade the same way
# migration 001 preserved data rather than resetting it. 'narrow' starts
# empty for existing users — not a regression, since a missing override
# already falls back to the dashboard.yaml default position.
_MIGRATION_008_WIDGET_LAYOUT_BREAKPOINT = """
CREATE TABLE IF NOT EXISTS widget_layout_new (
    user_id TEXT NOT NULL,
    breakpoint TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    layout TEXT NOT NULL,
    PRIMARY KEY (user_id, breakpoint, widget_id)
);

INSERT INTO widget_layout_new (user_id, breakpoint, widget_id, layout)
SELECT user_id, 'wide', widget_id, layout
FROM widget_layout
WHERE rowid IN (SELECT MAX(rowid) FROM widget_layout GROUP BY user_id, widget_id);

DROP TABLE widget_layout;
ALTER TABLE widget_layout_new RENAME TO widget_layout;
CREATE INDEX IF NOT EXISTS idx_widget_layout_widget_id ON widget_layout (widget_id);
"""


# `widget_layout` gained device_id back (see the table comment above):
# migration 008's breakpoint-only keying meant tiles rearranged on one device
# instantly rearranged on every other device at the same viewport class —
# reported as tiles from one device "leaking" onto another. SQLite can't
# ALTER a PRIMARY KEY, so this rebuilds under a temp name and swaps it in,
# same approach as migrations 001/008. Every existing device is seeded with a
# copy of its user's current (pre-migration, shared-by-breakpoint) layout —
# preserves what's actually visible today on every screen rather than
# resetting any of them to dashboard.yaml defaults or picking one device to
# "win" and blanking the rest.
_MIGRATION_009_WIDGET_LAYOUT_DEVICE = """
CREATE TABLE IF NOT EXISTS widget_layout_new (
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    breakpoint TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    layout TEXT NOT NULL,
    PRIMARY KEY (user_id, device_id, breakpoint, widget_id)
);

INSERT INTO widget_layout_new (user_id, device_id, breakpoint, widget_id, layout)
SELECT wl.user_id, d.id, wl.breakpoint, wl.widget_id, wl.layout
FROM widget_layout wl
CROSS JOIN devices d;

DROP TABLE widget_layout;
ALTER TABLE widget_layout_new RENAME TO widget_layout;
CREATE INDEX IF NOT EXISTS idx_widget_layout_widget_id ON widget_layout (widget_id);
"""


# `custom_widgets` gained owner_user_id/owner_device_id (see the table
# comment above) so a UI-added tile can be private to the (user, device) pair
# that created it instead of appearing for the whole household on every
# screen. No backfill: existing rows stay NULL/NULL, the grandfathered
# visible-to-everyone case — there's no historical owner to recover, and no
# tile that's currently visible somewhere should disappear on upgrade.
def _migration_010_custom_widget_ownership(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(custom_widgets)")}
    if "owner_user_id" not in columns:
        conn.execute("ALTER TABLE custom_widgets ADD COLUMN owner_user_id TEXT")
    if "owner_device_id" not in columns:
        conn.execute("ALTER TABLE custom_widgets ADD COLUMN owner_device_id TEXT")


# Seeds the new per-(user, device) `hidden_widget_ids` table from the old
# global `removed_widget_ids` table, cross-joined against every known (user,
# device) pair — so a widget that was globally hidden before this migration
# stays hidden everywhere immediately after upgrading, rather than
# reappearing on every screen. `removed_widget_ids` itself is left alone
# (nothing reads it anymore) rather than dropped — see that table's comment.
def _migration_011_seed_hidden_widget_ids(conn: sqlite3.Connection) -> None:
    removed = [row["widget_id"] for row in conn.execute("SELECT widget_id FROM removed_widget_ids")]
    if not removed:
        return
    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users")]
    device_ids = [row["id"] for row in conn.execute("SELECT id FROM devices")]
    conn.executemany(
        "INSERT INTO hidden_widget_ids (user_id, device_id, widget_id) VALUES (?, ?, ?) "
        "ON CONFLICT (user_id, device_id, widget_id) DO NOTHING",
        [(user_id, device_id, widget_id) for user_id in user_ids for device_id in device_ids for widget_id in removed],
    )


# `packages` gained user_id (see the table comment above) as part of moving
# package tracking from a single household-wide list to a per-user one (see
# app.plugins.packages.plugin). Existing untagged rows are backfilled to the
# household admin (the oldest-created one, same "promote the oldest"
# precedent as _migration_002_user_roles) rather than left ownerless — an
# ownerless row would simply become invisible once the packages API starts
# filtering by requesting user, silently dropping whatever was already being
# tracked.
def _migration_012_packages_user_id(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(packages)")}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE packages ADD COLUMN user_id TEXT")
    admin = conn.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1").fetchone()
    if admin is not None:
        conn.execute("UPDATE packages SET user_id = ? WHERE user_id IS NULL", (admin["id"],))
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_packages_widget_user ON packages (widget_id, user_id, delivered, eta_date)"
    )


# iCloud Photos moved from one shared admin-configured login (`app_settings`'
# icloud_username/icloud_password) to per-user credentials in the new
# `user_credentials` table (see that table's comment and app.plugins.photos).
# Seeds the admin's personal credential from whatever was previously the one
# global login, so the admin doesn't lose their configured photo library on
# upgrade — every other household member simply starts with no iCloud
# credential of their own, same as a fresh install. Reads/writes app_settings
# via raw SQL against this migration's own `conn` rather than
# get_app_settings/save_app_settings, which each open their own connection
# via `_connect()` and would contend with this function's open transaction
# (same reasoning as _migration_007_extract_network_integrations).
def _migration_013_seed_icloud_user_credentials(conn: sqlite3.Connection) -> None:
    rows = {
        row["key"]: row["value"]
        for row in conn.execute(
            "SELECT key, value FROM app_settings WHERE key IN ('icloud_username', 'icloud_password')"
        )
    }
    username = rows.get("icloud_username")
    if not username:
        return
    admin = conn.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1").fetchone()
    if admin is None:
        return
    encrypted_password = rows.get("icloud_password")
    password = decrypt(encrypted_password) if encrypted_password else None
    credentials = {"username": username, "password": encrypt(password) if password else None}
    conn.execute(
        "INSERT INTO user_credentials (user_id, provider, credentials) VALUES (?, 'icloud', ?) "
        "ON CONFLICT (user_id, provider) DO NOTHING",
        (admin["id"], json.dumps(credentials)),
    )


# `photo_index`/`photo_index_meta` gained a `user_id` column (see the table
# comment above) so an icloud_private widget indexes each connected household
# member's private library separately instead of one shared scan result
# clobbered by whichever user's background scan ran most recently (plan §7).
# SQLite can't ALTER a PRIMARY KEY, so both tables are rebuilt under a temp
# name and swapped in, same approach as migrations 001/008/009. Every
# existing row is backfilled under the '' shared-index sentinel: correct and
# final for local/icloud_shared/immich widgets (still one library for the
# whole household), and a harmless interim value for icloud_private widgets
# that gets replaced within moments by the real per-user scans the app
# schedules at startup — see app.plugins.photos.indexer.index_photos.
_MIGRATION_014_PHOTO_INDEX_USER_ID = """
CREATE TABLE IF NOT EXISTS photo_index_new (
    widget_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    photo_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    generation INTEGER NOT NULL,
    PRIMARY KEY (widget_id, user_id, photo_id)
);

INSERT INTO photo_index_new (widget_id, user_id, photo_id, position, generation)
SELECT widget_id, '', photo_id, position, generation FROM photo_index;

DROP TABLE photo_index;
ALTER TABLE photo_index_new RENAME TO photo_index;
CREATE INDEX IF NOT EXISTS idx_photo_index_widget_user_position ON photo_index (widget_id, user_id, position);

CREATE TABLE IF NOT EXISTS photo_index_meta_new (
    widget_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    generation INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    last_error TEXT,
    PRIMARY KEY (widget_id, user_id)
);

INSERT INTO photo_index_meta_new (widget_id, user_id, generation, updated_at, status, last_error)
SELECT widget_id, '', generation, updated_at, status, last_error FROM photo_index_meta;

DROP TABLE photo_index_meta;
ALTER TABLE photo_index_meta_new RENAME TO photo_index_meta;
"""


def _migration_015_deduplicate_device_names(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, name FROM devices ORDER BY created_at ASC, id ASC").fetchall()
    seen_normalized: set[str] = set()
    for row in rows:
        device_id = row[0]
        name = row[1]
        base_name = name.strip() if name and name.strip() else "New Device"
        normalized = base_name.casefold()
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            if base_name != name:
                conn.execute("UPDATE devices SET name = ? WHERE id = ?", (base_name, device_id))
        else:
            counter = 2
            candidate = f"{base_name} {counter}"
            while candidate.casefold() in seen_normalized:
                counter += 1
                candidate = f"{base_name} {counter}"
            seen_normalized.add(candidate.casefold())
            conn.execute("UPDATE devices SET name = ? WHERE id = ?", (candidate, device_id))


def _migration_016_weather_flights_network_scope(conn: sqlite3.Connection) -> None:
    """Migrates personal-scoped weather and flights settings back to network scope.

    Copies each user's configured settings for weather/flights widgets into
    widget_settings (prioritizing the admin user's row, if available) so
    existing deployments keep their configured location on upgrade, and
    cleans up the now-obsolete widget_user_settings rows.
    """
    custom_types = {row[0]: row[1] for row in conn.execute("SELECT id, type FROM custom_widgets")}
    user_roles = {row[0]: row[1] for row in conn.execute("SELECT id, role FROM users")}

    rows = conn.execute("SELECT user_id, widget_id, settings FROM widget_user_settings").fetchall()
    settings_by_widget: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        user_id, widget_id, settings = row[0], row[1], row[2]
        widget_type = custom_types.get(widget_id, widget_id)
        if widget_type in ("weather", "flights"):
            settings_by_widget.setdefault(widget_id, []).append((user_id, settings))

    for widget_id, user_entries in settings_by_widget.items():
        admin_entry = next((s for u_id, s in user_entries if user_roles.get(u_id) == "admin"), None)
        chosen_settings = admin_entry if admin_entry is not None else user_entries[0][1]

        conn.execute(
            "INSERT INTO widget_settings (widget_id, settings) VALUES (?, ?) "
            "ON CONFLICT (widget_id) DO UPDATE SET settings = excluded.settings",
            (widget_id, chosen_settings),
        )

    for row in rows:
        user_id, widget_id = row[0], row[1]
        widget_type = custom_types.get(widget_id, widget_id)
        if widget_type in ("weather", "flights"):
            conn.execute(
                "DELETE FROM widget_user_settings WHERE user_id = ? AND widget_id = ?",
                (user_id, widget_id),
            )


def _migration_017_weather_flights_personal_scope(conn: sqlite3.Connection) -> None:
    """Migrates weather and flights widget settings to personal user scope.

    Copies existing widget_settings for weather and flights widgets into
    widget_user_settings for all existing users (if not already present), so
    every user retains the configured location on upgrade.
    """
    custom_types = {row[0]: row[1] for row in conn.execute("SELECT id, type FROM custom_widgets")}
    users = [row[0] for row in conn.execute("SELECT id FROM users")]

    settings_rows = conn.execute("SELECT widget_id, settings FROM widget_settings").fetchall()
    for row in settings_rows:
        widget_id, settings = row[0], row[1]
        widget_type = custom_types.get(widget_id, widget_id)
        if widget_type in ("weather", "flights"):
            for user_id in users:
                conn.execute(
                    "INSERT INTO widget_user_settings (user_id, widget_id, settings) VALUES (?, ?, ?) "
                    "ON CONFLICT (user_id, widget_id) DO NOTHING",
                    (user_id, widget_id, settings),
                )


def _migration_018_clean_photos_widget_user_settings(conn: sqlite3.Connection) -> None:
    """PhotosPlugin settings are shared across the household in widget_settings.

    Deletes any legacy widget_user_settings rows for photos widgets so they
    cannot shadow widget_settings changes.
    """
    custom_types = {row[0]: row[1] for row in conn.execute("SELECT id, type FROM custom_widgets")}
    for row in conn.execute("SELECT user_id, widget_id FROM widget_user_settings").fetchall():
        user_id, widget_id = row[0], row[1]
        widget_type = custom_types.get(widget_id, widget_id)
        if widget_type == "photos":
            conn.execute(
                "DELETE FROM widget_user_settings WHERE user_id = ? AND widget_id = ?",
                (user_id, widget_id),
            )


_MIGRATIONS: tuple[str | Callable[[sqlite3.Connection], None], ...] = (
    _MIGRATION_001_USERS_DEVICES,
    _migration_002_user_roles,
    _migration_003_seed_personal_widget_settings,
    _migration_004_merge_container_widgets,
    _migration_005_seed_personal_sports_weather_settings,
    _migration_006_seed_rss_feed_catalog,
    _migration_007_extract_network_integrations,
    _MIGRATION_008_WIDGET_LAYOUT_BREAKPOINT,
    _MIGRATION_009_WIDGET_LAYOUT_DEVICE,
    _migration_010_custom_widget_ownership,
    _migration_011_seed_hidden_widget_ids,
    _migration_012_packages_user_id,
    _migration_013_seed_icloud_user_credentials,
    _MIGRATION_014_PHOTO_INDEX_USER_ID,
    _migration_015_deduplicate_device_names,
    _migration_016_weather_flights_network_scope,
    _migration_017_weather_flights_personal_scope,
    _migration_018_clean_photos_widget_user_settings,
)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Applies each un-run migration as its own atomic unit: that migration's
    writes and its `PRAGMA user_version` bump commit (or roll back) together,
    so a crash mid-migration leaves `user_version` pointing at the last
    migration that actually completed — a retried boot resumes from exactly
    that point instead of re-running (or skipping) one that may not be safe
    to repeat. The old behavior only bumped `user_version` once, after every
    migration in the list had run, so a crash partway through silently
    reverted to "none applied" on the next boot even though some had already
    written (and possibly weren't idempotent to rerun).

    Uses fully manual transaction control (`isolation_level = None`) rather
    than sqlite3's default implicit-BEGIN heuristic, because
    `executescript()` unconditionally issues a COMMIT before it runs —
    wrapping it in a caller-issued `conn.execute("BEGIN")` would just get
    silently committed away. Baking `BEGIN`/`COMMIT` into the script text
    itself (for script migrations) or driving them explicitly around the
    call (for callable migrations) sidesteps that entirely. The script
    branch has no explicit `except`/`ROLLBACK` of its own — if a later
    statement in the script fails, the transaction it opened is left
    pending on `conn`, and it's `init_db`'s enclosing `with _connect() as
    conn:` that rolls it back as the exception propagates out.
    """
    conn.isolation_level = None
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    for offset, migration in enumerate(_MIGRATIONS[current_version:]):
        version = current_version + offset + 1
        if callable(migration):
            conn.execute("BEGIN")
            try:
                migration(conn)
                conn.execute(f"PRAGMA user_version = {version}")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")
        else:
            conn.executescript(f"BEGIN;\n{migration}\nPRAGMA user_version = {version};\nCOMMIT;")


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


def record_speedtest_run(
    widget_id: str, download_mbps: float, upload_mbps: float, ping_ms: float, server_name: str
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO speedtest_runs (widget_id, ran_at, download_mbps, upload_mbps, ping_ms, server_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (widget_id, datetime.now(UTC).isoformat(), download_mbps, upload_mbps, ping_ms, server_name),
        )


def latest_speedtest_run(widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT ran_at, download_mbps, upload_mbps, ping_ms, server_name FROM speedtest_runs "
            "WHERE widget_id = ? ORDER BY ran_at DESC LIMIT 1",
            (widget_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def speedtest_run_history(widget_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ran_at, download_mbps, upload_mbps, ping_ms, server_name FROM speedtest_runs "
            "WHERE widget_id = ? ORDER BY ran_at DESC LIMIT ?",
            (widget_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def record_nasa_apod_fetch(widget_id: str, result: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO nasa_apod_fetches (widget_id, fetched_at, result) VALUES (?, ?, ?)",
            (widget_id, datetime.now(UTC).isoformat(), json.dumps(result)),
        )


def latest_nasa_apod_fetch(widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT fetched_at, result FROM nasa_apod_fetches WHERE widget_id = ? ORDER BY fetched_at DESC LIMIT 1",
            (widget_id,),
        ).fetchone()
    if row is None:
        return None
    return {"fetched_at": row["fetched_at"], **json.loads(row["result"])}


def save_widget_settings(widget_id: str, settings: dict[str, Any]) -> None:
    """Persist a widget's full settings dict, overwriting any prior override.

    Lets settings changed at runtime (e.g. the weather widget's city) survive
    a backend restart without editing dashboard.yaml.
    """
    with _connect() as conn:
        _upsert(conn, "widget_settings", {"widget_id": widget_id, "settings": json.dumps(settings)}, ("widget_id",))


def get_widget_settings(widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT settings FROM widget_settings WHERE widget_id = ?", (widget_id,)).fetchone()
    return None if row is None else json.loads(row["settings"])


def list_widget_settings() -> dict[str, dict[str, Any]]:
    """All widget_settings rows in one query, keyed by widget_id — for
    startup plugin loading, which otherwise calls `get_widget_settings` once
    per configured widget (one connection/query per widget)."""
    with _connect() as conn:
        rows = conn.execute("SELECT widget_id, settings FROM widget_settings").fetchall()
    return {row["widget_id"]: json.loads(row["settings"]) for row in rows}


# Settings keys within a network_integrations row's `settings` blob that get
# Fernet-encrypted per-value before being stored, mirroring
# SECRET_APP_SETTINGS_KEYS' whole-row encryption for app_settings — see
# app.crypto. Fixed across every integration type: only Jellyfin uses
# api_key, but reusing one constant keeps save/get_network_integration
# type-agnostic rather than needing a per-type secret-key table.
NETWORK_INTEGRATION_SECRET_KEYS = ("password", "api_key")


def _encrypt_network_integration_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return {k: (encrypt(v) if k in NETWORK_INTEGRATION_SECRET_KEYS and v else v) for k, v in settings.items()}


def _decrypt_network_integration_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return {k: (decrypt(v) if k in NETWORK_INTEGRATION_SECRET_KEYS and v else v) for k, v in settings.items()}


def save_network_integration(id: str, type_: str, name: str, settings: dict[str, Any]) -> None:
    """Create or overwrite a network integration row (its full settings, not a partial merge — callers merge first)."""
    stored = _encrypt_network_integration_settings(settings)
    with _connect() as conn:
        _upsert(
            conn,
            "network_integrations",
            {"id": id, "type": type_, "name": name, "settings": json.dumps(stored)},
            ("id",),
        )


def get_network_integration(id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT id, type, name, settings FROM network_integrations WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "type": row["type"],
        "name": row["name"],
        "settings": _decrypt_network_integration_settings(json.loads(row["settings"])),
    }


def list_network_integrations(type_: str | None = None) -> list[dict[str, Any]]:
    with _connect() as conn:
        if type_ is None:
            rows = conn.execute("SELECT id, type, name, settings FROM network_integrations").fetchall()
        else:
            rows = conn.execute(
                "SELECT id, type, name, settings FROM network_integrations WHERE type = ?", (type_,)
            ).fetchall()
    return [
        {
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "settings": _decrypt_network_integration_settings(json.loads(row["settings"])),
        }
        for row in rows
    ]


def delete_network_integration(id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM network_integrations WHERE id = ?", (id,))


def save_widget_layout(user_id: str, device_id: str, breakpoint: str, widget_id: str, layout: dict[str, Any]) -> None:
    """Persist a widget's grid position for a given (user, device, breakpoint), overwriting any prior override.

    Lets drag-to-rearrange edits made from the dashboard survive a backend
    restart without editing dashboard.yaml, the same way `save_widget_settings`
    does for runtime settings changes. Scoped per (user, device) — a "device
    settings" concern, see CONTRIBUTING.md — so rearranging one screen never
    touches another user's, or another screen's, arrangement.
    """
    with _connect() as conn:
        _upsert(
            conn,
            "widget_layout",
            {
                "user_id": user_id,
                "device_id": device_id,
                "breakpoint": breakpoint,
                "widget_id": widget_id,
                "layout": json.dumps(layout),
            },
            ("user_id", "device_id", "breakpoint", "widget_id"),
        )


def save_widget_layouts(entries: list[tuple[str, str, str, str, dict[str, Any]]]) -> None:
    """Batched `save_widget_layout` — one connection/transaction for the
    whole list instead of one per entry, for callers persisting an entire
    layout (e.g. a drag-to-rearrange save covering every widget on screen)."""
    with _connect() as conn:
        for user_id, device_id, breakpoint, widget_id, layout in entries:
            _upsert(
                conn,
                "widget_layout",
                {
                    "user_id": user_id,
                    "device_id": device_id,
                    "breakpoint": breakpoint,
                    "widget_id": widget_id,
                    "layout": json.dumps(layout),
                },
                ("user_id", "device_id", "breakpoint", "widget_id"),
            )


def get_widget_layout(user_id: str, device_id: str, breakpoint: str, widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT layout FROM widget_layout WHERE user_id = ? AND device_id = ? AND breakpoint = ? AND widget_id = ?",
            (user_id, device_id, breakpoint, widget_id),
        ).fetchone()
    return None if row is None else json.loads(row["layout"])


def delete_widget_layout_for_widget(widget_id: str) -> None:
    """Drop every (user, device, breakpoint) layout override for a widget that's been removed."""
    with _connect() as conn:
        conn.execute("DELETE FROM widget_layout WHERE widget_id = ?", (widget_id,))


def list_widget_layouts(user_id: str, device_id: str, breakpoint: str) -> dict[str, dict[str, Any]]:
    """All layout overrides for a (user, device, breakpoint), keyed by widget_id.

    One query for the whole dashboard list rather than one per widget.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT widget_id, layout FROM widget_layout WHERE user_id = ? AND device_id = ? AND breakpoint = ?",
            (user_id, device_id, breakpoint),
        ).fetchall()
    return {row["widget_id"]: json.loads(row["layout"]) for row in rows}


_DEFAULT_SCREENSAVER_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "idle_timeout_seconds": 300,
    "rotation_interval_seconds": 25,
    "widget_ids": [],
    "text_animation_style": "marquee",
    "led_color": "#ff8a00",
    "text_pause_seconds": 8,
    "flipboard_pattern": "top_to_bottom",
}


def get_screensaver_settings(user_id: str, device_id: str) -> dict[str, Any]:
    """A (user, device)'s screensaver settings, defaults filled in for anything unset.

    Same shape as `get_user_preferences`: defaults live here so callers (and
    a brand-new row) never have to special-case a missing key.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT settings FROM screensaver_settings WHERE user_id = ? AND device_id = ?",
            (user_id, device_id),
        ).fetchone()
    overrides = json.loads(row["settings"]) if row else {}
    return {**_DEFAULT_SCREENSAVER_SETTINGS, **overrides}


def save_screensaver_settings(user_id: str, device_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge `overrides` onto a (user, device)'s stored screensaver settings and persist the result.

    Same merge-upsert shape as `save_user_preferences` — lets the API layer
    send a partial PATCH body without first reading the current value.
    """
    merged = {**get_screensaver_settings(user_id, device_id), **overrides}
    with _connect() as conn:
        _upsert(
            conn,
            "screensaver_settings",
            {"user_id": user_id, "device_id": device_id, "settings": json.dumps(merged)},
            ("user_id", "device_id"),
        )
    return merged


def save_widget_user_settings(user_id: str, widget_id: str, settings: dict[str, Any]) -> None:
    """Persist a (user, widget) settings override, overwriting any prior one.

    Same overwrite-upsert shape as `save_widget_settings`, but scoped to a
    single household member — for "personal"-scope plugins (RSS, calendar)
    where the same widget_id should render different content per user.
    """
    with _connect() as conn:
        _upsert(
            conn,
            "widget_user_settings",
            {"user_id": user_id, "widget_id": widget_id, "settings": json.dumps(settings)},
            ("user_id", "widget_id"),
        )


def get_widget_user_settings(user_id: str, widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT settings FROM widget_user_settings WHERE user_id = ? AND widget_id = ?",
            (user_id, widget_id),
        ).fetchone()
    return None if row is None else json.loads(row["settings"])


def delete_widget_user_settings_for_widget(widget_id: str) -> None:
    """Drop every user's settings override for a widget that's been removed."""
    with _connect() as conn:
        conn.execute("DELETE FROM widget_user_settings WHERE widget_id = ?", (widget_id,))


def delete_widget_user_settings_for_user(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM widget_user_settings WHERE user_id = ?", (user_id,))


def save_widget_device_settings(device_id: str, widget_id: str, settings: dict[str, Any]) -> None:
    """Persist a (device, widget) settings override, overwriting any prior one.

    Scoped to a single physical device — for settings keys a plugin lists in
    `device_overridable_settings` (e.g. Jellyfin's playback_mode), where the
    right value depends on that device's hardware/browser, not who's logged
    in or the household's shared default.
    """
    with _connect() as conn:
        _upsert(
            conn,
            "widget_device_settings",
            {"device_id": device_id, "widget_id": widget_id, "settings": json.dumps(settings)},
            ("device_id", "widget_id"),
        )


def get_widget_device_settings(device_id: str, widget_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT settings FROM widget_device_settings WHERE device_id = ? AND widget_id = ?",
            (device_id, widget_id),
        ).fetchone()
    return None if row is None else json.loads(row["settings"])


def delete_widget_device_settings(device_id: str, widget_id: str) -> None:
    """Reset a single device's override for a widget back to the household default."""
    with _connect() as conn:
        conn.execute("DELETE FROM widget_device_settings WHERE device_id = ? AND widget_id = ?", (device_id, widget_id))


def delete_widget_device_settings_for_widget(widget_id: str) -> None:
    """Drop every device's settings override for a widget that's been removed."""
    with _connect() as conn:
        conn.execute("DELETE FROM widget_device_settings WHERE widget_id = ?", (widget_id,))


def begin_photo_index_scan(widget_id: str, user_id: str = "") -> int:
    """Mints a new generation tag for a background photo-index scan of
    (widget_id, user_id) — user_id is the '' shared-index sentinel for every
    provider except icloud_private, where it's the household member whose
    private library this particular scan is for (see
    PhotosPlugin._photo_index_user_id). Every chunk upserted during this scan
    must use this generation so `finish_photo_index_scan` can identify (and
    delete) rows left over from a previous scan.

    Uses the monotonic clock at nanosecond resolution rather than
    millisecond-truncated wall-clock time — two scans of a small photo
    source can legitimately complete within the same millisecond (more so
    now that WAL mode makes each write faster), and a collision here would
    make `finish_photo_index_scan` treat the newer scan's own rows as
    leftovers from the older one, deleting nothing stale.
    """
    return time.monotonic_ns()


def upsert_photo_index_chunk(
    widget_id: str, generation: int, photo_ids: list[str], start_position: int, user_id: str = ""
) -> None:
    """Upserts one chunk of photo_ids (already in enumeration order) for an
    in-progress (widget_id, user_id) scan. Safe to call multiple times per
    scan — each call is its own committed transaction, so a concurrent
    reader only ever sees a growing superset of the previous good index,
    never a truncated one.
    """
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO photo_index (widget_id, user_id, photo_id, position, generation) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (widget_id, user_id, photo_id) DO UPDATE SET "
            "position = excluded.position, generation = excluded.generation",
            [
                (widget_id, user_id, photo_id, start_position + offset, generation)
                for offset, photo_id in enumerate(photo_ids)
            ],
        )


def finish_photo_index_scan(widget_id: str, generation: int, user_id: str = "") -> None:
    """Drops any (widget_id, user_id) photo_index row not written by
    `generation` (i.e. photos removed from the source since the last scan),
    then marks the scan as successful.
    """
    with _connect() as conn:
        conn.execute(
            "DELETE FROM photo_index WHERE widget_id = ? AND user_id = ? AND generation != ?",
            (widget_id, user_id, generation),
        )
        conn.execute(
            "INSERT INTO photo_index_meta (widget_id, user_id, generation, updated_at, status, last_error) "
            "VALUES (?, ?, ?, ?, 'ok', NULL) "
            "ON CONFLICT (widget_id, user_id) DO UPDATE SET generation = excluded.generation, "
            "updated_at = excluded.updated_at, status = 'ok', last_error = NULL",
            (widget_id, user_id, generation, datetime.now(UTC).isoformat()),
        )


def mark_photo_index_scan_failed(widget_id: str, error: str, user_id: str = "") -> None:
    """Records a failed (widget_id, user_id) scan without touching
    photo_index rows, so the previous good index (if any) keeps serving reads.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO photo_index_meta (widget_id, user_id, generation, updated_at, status, last_error) "
            "VALUES (?, ?, 0, ?, 'error', ?) "
            "ON CONFLICT (widget_id, user_id) DO UPDATE SET updated_at = excluded.updated_at, "
            "status = 'error', last_error = excluded.last_error",
            (widget_id, user_id, datetime.now(UTC).isoformat(), error),
        )


def photo_index_photo_ids(widget_id: str, user_id: str = "") -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT photo_id FROM photo_index WHERE widget_id = ? AND user_id = ? ORDER BY position ASC",
            (widget_id, user_id),
        ).fetchall()
    return [row["photo_id"] for row in rows]


def photo_index_status(widget_id: str, user_id: str = "") -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT widget_id, generation, updated_at, status, last_error FROM photo_index_meta "
            "WHERE widget_id = ? AND user_id = ?",
            (widget_id, user_id),
        ).fetchone()
    return None if row is None else dict(row)


def delete_photo_index(widget_id: str) -> None:
    """Drops every user's index rows for widget_id — used when the widget
    itself is deleted, so intentionally not scoped to a single user_id.
    """
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
    return {
        row["key"]: (decrypt(row["value"]) if row["key"] in SECRET_APP_SETTINGS_KEYS else row["value"]) for row in rows
    }


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


def has_seen_severe_weather_alert(widget_id: str, alert_key: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM severe_weather_seen WHERE widget_id = ? AND alert_key = ?",
            (widget_id, alert_key),
        ).fetchone()
    return row is not None


def mark_severe_weather_alert_seen(widget_id: str, alert_key: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO severe_weather_seen (widget_id, alert_key, first_seen_at) VALUES (?, ?, ?)",
            (widget_id, alert_key, datetime.now(UTC).isoformat()),
        )


_CHORE_COLUMNS = "id, widget_id, user_id, text, completed, created_at, completed_at"


def add_chore(widget_id: str, user_id: str, text: str) -> dict[str, Any]:
    created_at = datetime.now(UTC).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO chores (widget_id, user_id, text, completed, created_at, completed_at) "
            "VALUES (?, ?, ?, 0, ?, NULL)",
            (widget_id, user_id, text, created_at),
        )
        chore_id = cursor.lastrowid
    return {
        "id": chore_id,
        "widget_id": widget_id,
        "user_id": user_id,
        "text": text,
        "completed": False,
        "created_at": created_at,
        "completed_at": None,
    }


def list_chores(widget_id: str, user_id: str) -> list[dict[str, Any]]:
    """A user's items on `widget_id`'s list, open items first, oldest first within each group."""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {_CHORE_COLUMNS} FROM chores WHERE widget_id = ? AND user_id = ? "
            "ORDER BY completed ASC, created_at ASC",
            (widget_id, user_id),
        ).fetchall()
    return [dict(row) | {"completed": bool(row["completed"])} for row in rows]


def complete_chore(chore_id: int, user_id: str) -> dict[str, Any] | None:
    """Toggle a chore's completed state, scoped to `user_id` so one user can't toggle another's item.

    Returns the updated row, or None if no chore with that id belongs to this user.
    """
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_CHORE_COLUMNS} FROM chores WHERE id = ? AND user_id = ?", (chore_id, user_id)
        ).fetchone()
        if row is None:
            return None
        if bool(row["completed"]):
            conn.execute(
                "UPDATE chores SET completed = 0, completed_at = NULL WHERE id = ? AND user_id = ?",
                (chore_id, user_id),
            )
        else:
            completed_at = datetime.now(UTC).isoformat()
            conn.execute(
                "UPDATE chores SET completed = 1, completed_at = ? WHERE id = ? AND user_id = ?",
                (completed_at, chore_id, user_id),
            )
        row = conn.execute(f"SELECT {_CHORE_COLUMNS} FROM chores WHERE id = ?", (chore_id,)).fetchone()
    return dict(row) | {"completed": bool(row["completed"])}


def remove_chore(chore_id: int, user_id: str) -> dict[str, Any] | None:
    """Delete a chore, scoped to `user_id`. Returns the deleted row, or None if not found/not owned."""
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_CHORE_COLUMNS} FROM chores WHERE id = ? AND user_id = ?", (chore_id, user_id)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM chores WHERE id = ?", (chore_id,))
    return dict(row) | {"completed": bool(row["completed"])}


_SHOPPING_COLUMNS = "id, widget_id, text, checked, added_by, checked_by, created_at, checked_at"


def add_shopping_item(widget_id: str, text: str, added_by: str) -> dict[str, Any]:
    created_at = datetime.now(UTC).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO shopping_items (widget_id, text, checked, added_by, checked_by, created_at, checked_at) "
            "VALUES (?, ?, 0, ?, NULL, ?, NULL)",
            (widget_id, text, added_by, created_at),
        )
        item_id = cursor.lastrowid
    return {
        "id": item_id,
        "widget_id": widget_id,
        "text": text,
        "checked": False,
        "added_by": added_by,
        "checked_by": None,
        "created_at": created_at,
        "checked_at": None,
    }


def list_shopping_items(widget_id: str) -> list[dict[str, Any]]:
    """A widget's shared list, unchecked items first, oldest first within each group."""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {_SHOPPING_COLUMNS} FROM shopping_items WHERE widget_id = ? ORDER BY checked ASC, created_at ASC",
            (widget_id,),
        ).fetchall()
    return [dict(row) | {"checked": bool(row["checked"])} for row in rows]


def check_shopping_item(item_id: int, checked_by: str) -> dict[str, Any] | None:
    """Toggle a shopping item's checked state. Returns the updated row, or None if not found."""
    with _connect() as conn:
        row = conn.execute(f"SELECT {_SHOPPING_COLUMNS} FROM shopping_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        if bool(row["checked"]):
            conn.execute(
                "UPDATE shopping_items SET checked = 0, checked_by = NULL, checked_at = NULL WHERE id = ?",
                (item_id,),
            )
        else:
            checked_at = datetime.now(UTC).isoformat()
            conn.execute(
                "UPDATE shopping_items SET checked = 1, checked_by = ?, checked_at = ? WHERE id = ?",
                (checked_by, checked_at, item_id),
            )
        row = conn.execute(f"SELECT {_SHOPPING_COLUMNS} FROM shopping_items WHERE id = ?", (item_id,)).fetchone()
    return dict(row) | {"checked": bool(row["checked"])}


def remove_shopping_item(item_id: int) -> dict[str, Any] | None:
    """Delete a shopping item. Returns the deleted row, or None if not found."""
    with _connect() as conn:
        row = conn.execute(f"SELECT {_SHOPPING_COLUMNS} FROM shopping_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
    return dict(row) | {"checked": bool(row["checked"])}


_RSS_FEED_COLUMNS = "id, user_id, url, name, item_limit, created_at"


def add_rss_feed(user_id: str, url: str, name: str | None, item_limit: int = 10) -> dict[str, Any]:
    """Add a feed to a user's catalog. Adding a URL already in that user's
    catalog is idempotent — it returns the existing entry unchanged rather
    than erroring or duplicating it, since the (user_id, url) unique
    constraint makes "add" and "get-or-create" the same operation here."""
    created_at = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO rss_feeds (user_id, url, name, item_limit, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (user_id, url) DO NOTHING",
            (user_id, url, name, item_limit, created_at),
        )
        row = conn.execute(
            f"SELECT {_RSS_FEED_COLUMNS} FROM rss_feeds WHERE user_id = ? AND url = ?", (user_id, url)
        ).fetchone()
    return dict(row)


def list_rss_feeds(user_id: str) -> list[dict[str, Any]]:
    """A user's whole feed catalog, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {_RSS_FEED_COLUMNS} FROM rss_feeds WHERE user_id = ? ORDER BY created_at ASC", (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_rss_feeds(user_id: str, feed_ids: list[int]) -> list[dict[str, Any]]:
    """The subset of `feed_ids` that belong to this user, in catalog order.
    Ids that don't exist or belong to someone else are silently dropped —
    used to resolve a tile's selected feeds, where a since-deleted feed
    should just mean one fewer group rather than an error."""
    if not feed_ids:
        return []
    placeholders = ",".join("?" * len(feed_ids))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {_RSS_FEED_COLUMNS} FROM rss_feeds WHERE user_id = ? AND id IN ({placeholders}) "
            "ORDER BY created_at ASC",
            (user_id, *feed_ids),
        ).fetchall()
    return [dict(row) for row in rows]


def update_rss_feed(user_id: str, feed_id: int, name: str | None, item_limit: int) -> dict[str, Any] | None:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE rss_feeds SET name = ?, item_limit = ? WHERE id = ? AND user_id = ?",
            (name, item_limit, feed_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(f"SELECT {_RSS_FEED_COLUMNS} FROM rss_feeds WHERE id = ?", (feed_id,)).fetchone()
    return dict(row)


def delete_rss_feed(user_id: str, feed_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM rss_feeds WHERE id = ? AND user_id = ?", (feed_id, user_id))


# Keys within a user_credentials row's `credentials` blob that get
# Fernet-encrypted per-value before being stored — same mechanism as
# NETWORK_INTEGRATION_SECRET_KEYS above, just for the per-user analogue.
USER_CREDENTIAL_SECRET_KEYS = ("password",)


def _encrypt_user_credentials(credentials: dict[str, Any]) -> dict[str, Any]:
    return {k: (encrypt(v) if k in USER_CREDENTIAL_SECRET_KEYS and v else v) for k, v in credentials.items()}


def _decrypt_user_credentials(credentials: dict[str, Any]) -> dict[str, Any]:
    return {k: (decrypt(v) if k in USER_CREDENTIAL_SECRET_KEYS and v else v) for k, v in credentials.items()}


def save_user_credentials(user_id: str, provider: str, credentials: dict[str, Any]) -> None:
    """Create or overwrite a user's credentials for `provider` (its full value, not a partial merge)."""
    stored = _encrypt_user_credentials(credentials)
    with _connect() as conn:
        _upsert(
            conn,
            "user_credentials",
            {"user_id": user_id, "provider": provider, "credentials": json.dumps(stored)},
            ("user_id", "provider"),
        )


def get_user_credentials(user_id: str, provider: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT credentials FROM user_credentials WHERE user_id = ? AND provider = ?", (user_id, provider)
        ).fetchone()
    return None if row is None else _decrypt_user_credentials(json.loads(row["credentials"]))


def delete_user_credentials(user_id: str, provider: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM user_credentials WHERE user_id = ? AND provider = ?", (user_id, provider))


def list_user_ids_with_credentials(provider: str) -> list[str]:
    """Every user who has connected a `provider` credential — used by the
    background photo indexer to fan out one scan per household member with
    an icloud_private connection, instead of a single shared scan.
    """
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM user_credentials WHERE provider = ?", (provider,)).fetchall()
    return [row["user_id"] for row in rows]


_PACKAGE_COLUMNS = (
    "id, widget_id, user_id, tracking_number, carrier, label, status, last_event, eta_date, delivered, "
    "added_at, updated_at"
)


def add_package(widget_id: str, user_id: str, tracking_number: str, label: str | None = None) -> dict[str, Any]:
    added_at = datetime.now(UTC).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO packages "
            "(widget_id, user_id, tracking_number, carrier, label, status, last_event, eta_date, delivered, "
            "added_at, updated_at) "
            "VALUES (?, ?, ?, NULL, ?, NULL, NULL, NULL, 0, ?, NULL)",
            (widget_id, user_id, tracking_number, label, added_at),
        )
        package_id = cursor.lastrowid
    return {
        "id": package_id,
        "widget_id": widget_id,
        "user_id": user_id,
        "tracking_number": tracking_number,
        "carrier": None,
        "label": label,
        "status": None,
        "last_event": None,
        "eta_date": None,
        "delivered": False,
        "added_at": added_at,
        "updated_at": None,
    }


def list_packages(widget_id: str, user_id: str) -> list[dict[str, Any]]:
    """A (widget, user)'s tracked packages, active (not yet delivered) first, earliest ETA first within each group.

    Scoped per user (see the packages table comment) — each household member
    tracks their own deliveries, so this only returns the requesting user's
    packages for the widget, not every user's.
    """
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {_PACKAGE_COLUMNS} FROM packages WHERE widget_id = ? AND user_id = ? "
            "ORDER BY delivered ASC, eta_date IS NULL, eta_date ASC, added_at ASC",
            (widget_id, user_id),
        ).fetchall()
    return [dict(row) | {"delivered": bool(row["delivered"])} for row in rows]


def list_all_packages_for_widget(widget_id: str) -> list[dict[str, Any]]:
    """Every user's tracked packages for a widget, regardless of owner.

    Used only by the background 17Track refresh job (see
    app.scheduler.refresh_package_widget) — deliveries keep getting tracked
    for every household member even while nobody's actively viewing the
    widget; `list_packages` above is for the per-viewer read path, which
    filters to just the requesting user.
    """
    with _connect() as conn:
        rows = conn.execute(f"SELECT {_PACKAGE_COLUMNS} FROM packages WHERE widget_id = ?", (widget_id,)).fetchall()
    return [dict(row) | {"delivered": bool(row["delivered"])} for row in rows]


def get_package(package_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(f"SELECT {_PACKAGE_COLUMNS} FROM packages WHERE id = ?", (package_id,)).fetchone()
    return None if row is None else dict(row) | {"delivered": bool(row["delivered"])}


def remove_package(package_id: int) -> dict[str, Any] | None:
    """Delete a tracked package. Returns the deleted row, or None if not found."""
    with _connect() as conn:
        row = conn.execute(f"SELECT {_PACKAGE_COLUMNS} FROM packages WHERE id = ?", (package_id,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    return dict(row) | {"delivered": bool(row["delivered"])}


def update_package_status(
    package_id: int,
    carrier: str | None = None,
    status: str | None = None,
    last_event: str | None = None,
    eta_date: str | None = None,
    delivered: bool | None = None,
) -> dict[str, Any] | None:
    """Apply a 17Track refresh's results to a package row.

    Each param defaults to None meaning "leave unchanged" — a refresh only
    overwrites fields 17Track actually returned a value for, so a
    momentarily-thin API response can't blank out previously-known status.
    """
    with _connect() as conn:
        existing = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
        if existing is None:
            return None
        conn.execute(
            "UPDATE packages SET "
            "carrier = COALESCE(?, carrier), "
            "status = COALESCE(?, status), "
            "last_event = COALESCE(?, last_event), "
            "eta_date = COALESCE(?, eta_date), "
            "delivered = COALESCE(?, delivered), "
            "updated_at = ? "
            "WHERE id = ?",
            (
                carrier,
                status,
                last_event,
                eta_date,
                None if delivered is None else int(delivered),
                datetime.now(UTC).isoformat(),
                package_id,
            ),
        )
        row = conn.execute(f"SELECT {_PACKAGE_COLUMNS} FROM packages WHERE id = ?", (package_id,)).fetchone()
    return dict(row) | {"delivered": bool(row["delivered"])}


def save_oauth_tokens(
    provider: str, refresh_token: str, access_token: str | None = None, expires_at: str | None = None
) -> None:
    with _connect() as conn:
        _upsert(
            conn,
            "oauth_tokens",
            {
                "provider": provider,
                "refresh_token": refresh_token,
                "access_token": access_token,
                "expires_at": expires_at,
            },
            ("provider",),
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


def save_custom_widget(
    widget_id: str,
    type_: str,
    layout: dict[str, Any],
    tab: str | None,
    owner_user_id: str | None = None,
    owner_device_id: str | None = None,
) -> None:
    """Persist a widget added via the UI (no dashboard.yaml entry to live in).

    A widget added through `POST /api/widgets` always passes both owner_* —
    private to the (user, device) pair that created it (see
    app.api.widgets.add_widget). The None default exists only for
    migration/test convenience representing the legacy pre-ownership,
    visible-to-everyone case (see the custom_widgets table comment).
    """
    with _connect() as conn:
        _upsert(
            conn,
            "custom_widgets",
            {
                "id": widget_id,
                "type": type_,
                "layout": json.dumps(layout),
                "tab": tab,
                "owner_user_id": owner_user_id,
                "owner_device_id": owner_device_id,
            },
            ("id",),
        )


def delete_custom_widget(widget_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM custom_widgets WHERE id = ?", (widget_id,))


def list_custom_widgets() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, layout, tab, owner_user_id, owner_device_id FROM custom_widgets"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "type": row["type"],
            "layout": json.loads(row["layout"]),
            "tab": row["tab"],
            "owner_user_id": row["owner_user_id"],
            "owner_device_id": row["owner_device_id"],
        }
        for row in rows
    ]


def save_widget_custom_name(widget_id: str, name: str) -> None:
    with _connect() as conn:
        _upsert(conn, "widget_custom_names", {"widget_id": widget_id, "custom_name": name}, ("widget_id",))


def clear_widget_custom_name(widget_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM widget_custom_names WHERE widget_id = ?", (widget_id,))


def list_widget_custom_names() -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute("SELECT widget_id, custom_name FROM widget_custom_names").fetchall()
    return {row["widget_id"]: row["custom_name"] for row in rows}


def mark_widget_removed(widget_id: str) -> None:
    """Soft-delete a dashboard.yaml-defined widget — the file itself is left alone.

    Superseded by hide_widget below (see the removed_widget_ids table
    comment) — no remaining caller, kept only so migration 011 has a stable
    function-free (raw-SQL) history to seed from; new code should call
    hide_widget instead.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO removed_widget_ids (widget_id) VALUES (?) ON CONFLICT (widget_id) DO NOTHING",
            (widget_id,),
        )


def hide_widget(user_id: str, device_id: str, widget_id: str) -> None:
    """Hide a shared/legacy-global widget from just this (user, device)'s own widget list.

    Not a delete — the widget still exists and is still visible to everyone
    else. See app.api.widgets.remove_widget for when this is used instead of
    an actual delete.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO hidden_widget_ids (user_id, device_id, widget_id) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, device_id, widget_id) DO NOTHING",
            (user_id, device_id, widget_id),
        )


def hidden_widget_ids(user_id: str, device_id: str) -> set[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT widget_id FROM hidden_widget_ids WHERE user_id = ? AND device_id = ?", (user_id, device_id)
        ).fetchall()
    return {row["widget_id"] for row in rows}


def delete_hidden_widget_ids_for_widget(widget_id: str) -> None:
    """Drop every (user, device)'s hidden-state for a widget that's been fully deleted."""
    with _connect() as conn:
        conn.execute("DELETE FROM hidden_widget_ids WHERE widget_id = ?", (widget_id,))


def save_app_settings(overrides: dict[str, str | None]) -> None:
    """Upsert app setting overrides; a `None` value clears that key.

    Values for SECRET_APP_SETTINGS_KEYS (API keys, OAuth secrets, CalDAV/
    iCloud passwords) are encrypted before hitting disk — see app.crypto.
    """
    with _connect() as conn:
        for key, value in overrides.items():
            if value is None:
                conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            else:
                stored = encrypt(value) if key in SECRET_APP_SETTINGS_KEYS else value
                _upsert(conn, "app_settings", {"key": key, "value": stored}, ("key",))


# --- Users, devices, sessions, preferences -------------------------------
#
# No FK constraints here, matching the rest of this schema (no table in
# `_SCHEMA` uses one, and `_connect()` never sets `PRAGMA foreign_keys=ON`).
# Cascades on delete are driven by the two registries below instead of a
# hand-written DELETE per table in delete_user/delete_device — a new
# per-user or per-device table only needs a tuple added here, rather than
# relying on whoever adds that table to remember to also go edit these two
# functions (easy to miss, and nothing would catch it if they did).

_USER_SCOPED_TABLES: tuple[tuple[str, str], ...] = (
    ("sessions", "user_id"),
    ("widget_layout", "user_id"),
    ("widget_user_settings", "user_id"),
    ("screensaver_settings", "user_id"),
    ("user_preferences", "user_id"),
    ("hidden_widget_ids", "user_id"),
    ("packages", "user_id"),
    ("user_credentials", "user_id"),
)

_DEVICE_SCOPED_TABLES: tuple[tuple[str, str], ...] = (
    ("sessions", "device_id"),
    ("widget_device_settings", "device_id"),
    ("screensaver_settings", "device_id"),
    ("widget_layout", "device_id"),
    ("hidden_widget_ids", "device_id"),
)


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
        for table, column in _USER_SCOPED_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (user_id,))
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
        for table, column in _DEVICE_SCOPED_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (device_id,))
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


_DEFAULT_PREFERENCES: dict[str, Any] = {
    "theme": "dark",
    "voice_provider": "browser",
    "voice_id": "",
    "voice_name": "",
    "locale": "en",
    "location": None,
    "always_on_mic": False,
}


def get_user_preferences(user_id: str) -> dict[str, Any]:
    with _connect() as conn:
        row = conn.execute("SELECT preferences FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    overrides = json.loads(row["preferences"]) if row else {}
    return {**_DEFAULT_PREFERENCES, **overrides}


def save_user_preferences(user_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge `overrides` onto the user's stored preferences and persist the result."""
    merged = {**get_user_preferences(user_id), **overrides}
    with _connect() as conn:
        _upsert(conn, "user_preferences", {"user_id": user_id, "preferences": json.dumps(merged)}, ("user_id",))
    return merged


def get_tile_report_stats() -> dict[str, dict[str, Any]]:
    """Aggregate per-widget database metrics for the tile reporting page."""
    with _connect() as conn:
        chores_rows = conn.execute(
            "SELECT widget_id, COUNT(*) as total, SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as active "
            "FROM chores GROUP BY widget_id"
        ).fetchall()
        shopping_rows = conn.execute(
            "SELECT widget_id, COUNT(*) as total, SUM(CASE WHEN checked = 0 THEN 1 ELSE 0 END) as active "
            "FROM shopping_items GROUP BY widget_id"
        ).fetchall()
        alerts_rows = conn.execute(
            "SELECT widget_id, COUNT(*) as active FROM alerts WHERE dismissed = 0 GROUP BY widget_id"
        ).fetchall()
        photo_rows = conn.execute("SELECT widget_id, COUNT(*) as total FROM photo_index GROUP BY widget_id").fetchall()
        packages_rows = conn.execute("SELECT widget_id, COUNT(*) as total FROM packages GROUP BY widget_id").fetchall()
        custom_settings = {row["widget_id"] for row in conn.execute("SELECT widget_id FROM widget_settings").fetchall()}
        user_settings = {
            row["widget_id"] for row in conn.execute("SELECT DISTINCT widget_id FROM widget_user_settings").fetchall()
        }
        device_settings = {
            row["widget_id"] for row in conn.execute("SELECT DISTINCT widget_id FROM widget_device_settings").fetchall()
        }
        layout_overrides = {
            row["widget_id"] for row in conn.execute("SELECT DISTINCT widget_id FROM widget_layout").fetchall()
        }

    all_ids: set[str] = (
        {r["widget_id"] for r in chores_rows}
        | {r["widget_id"] for r in shopping_rows}
        | {r["widget_id"] for r in alerts_rows}
        | {r["widget_id"] for r in photo_rows}
        | {r["widget_id"] for r in packages_rows}
        | custom_settings
        | user_settings
        | device_settings
        | layout_overrides
    )

    chores_map = {r["widget_id"]: {"total": r["total"], "active": r["active"]} for r in chores_rows}
    shopping_map = {r["widget_id"]: {"total": r["total"], "active": r["active"]} for r in shopping_rows}
    alerts_map = {r["widget_id"]: r["active"] for r in alerts_rows}
    photo_map = {r["widget_id"]: r["total"] for r in photo_rows}
    packages_map = {r["widget_id"]: r["total"] for r in packages_rows}

    result: dict[str, dict[str, Any]] = {}
    for wid in all_ids:
        chores_info = chores_map.get(wid, {"total": 0, "active": 0})
        shopping_info = shopping_map.get(wid, {"total": 0, "active": 0})
        result[wid] = {
            "chores_active": chores_info["active"],
            "chores_total": chores_info["total"],
            "shopping_active": shopping_info["active"],
            "shopping_total": shopping_info["total"],
            "alerts_active": alerts_map.get(wid, 0),
            "photos_count": photo_map.get(wid, 0),
            "packages_count": packages_map.get(wid, 0),
            "has_custom_settings": wid in custom_settings,
            "has_user_settings": wid in user_settings,
            "has_device_settings": wid in device_settings,
            "has_layout_overrides": wid in layout_overrides,
        }
    return result
