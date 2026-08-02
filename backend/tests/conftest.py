from __future__ import annotations

import pytest

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


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point app.storage.db at an isolated sqlite file for this test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    return db_path
