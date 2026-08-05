from __future__ import annotations

import pytest

from app import config
from app.plugins.base import registry
from app.storage import db
from app.storage.cache import cache


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """The plugin registry and TTL cache are process-wide singletons; tests
    must not leak registrations or cached values into each other."""
    registry._plugins.clear()
    cache._store.clear()
    yield
    registry._plugins.clear()
    cache._store.clear()


@pytest.fixture(autouse=True)
def _reset_ambient_settings(monkeypatch):
    """`app.config.settings` is a process-wide singleton loaded once from
    `.env` at import time. A developer's local `.env` commonly carries real
    provider API keys for manual testing, so tests must not see them —
    otherwise results (e.g. `has_<key>` flags) depend on whichever secrets
    happen to be configured on the machine running the suite."""
    for key in config.APP_SETTINGS_KEYS:
        monkeypatch.setattr(config.settings, key, config.Settings.model_fields[key].default, raising=False)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point app.storage.db at an isolated sqlite file for this test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    return db_path
