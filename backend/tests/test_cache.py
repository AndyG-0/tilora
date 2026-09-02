from __future__ import annotations

from app.storage.cache import TTLCache


def test_get_missing_key_returns_none():
    cache = TTLCache()
    assert cache.get("missing") is None


def test_set_then_get_returns_value():
    cache = TTLCache()
    cache.set("key", {"a": 1}, ttl_seconds=60)
    assert cache.get("key") == {"a": 1}


def test_expired_entry_returns_none_and_is_evicted(monkeypatch):
    cache = TTLCache()
    times = iter([100.0, 200.0])
    monkeypatch.setattr("app.storage.cache.time.monotonic", lambda: next(times))

    cache.set("key", "value", ttl_seconds=10)  # expires_at = 110.0
    assert cache.get("key") is None  # "now" = 200.0, past expiry
    assert "key" not in cache._store


def test_delete_removes_entry():
    cache = TTLCache()
    cache.set("key", "value", ttl_seconds=60)

    cache.delete("key")

    assert cache.get("key") is None


def test_delete_missing_key_is_a_noop():
    cache = TTLCache()
    cache.delete("missing")  # should not raise


def test_sweep_expired_drops_only_expired_keys(monkeypatch):
    cache = TTLCache()
    monkeypatch.setattr("app.storage.cache.time.monotonic", lambda: 100.0)
    cache.set("expiring", "value", ttl_seconds=10)  # expires_at = 110.0
    cache.set("fresh", "value", ttl_seconds=1000)  # expires_at = 1100.0

    monkeypatch.setattr("app.storage.cache.time.monotonic", lambda: 200.0)
    dropped = cache.sweep_expired()

    assert dropped == 1
    assert "expiring" not in cache._store
    assert cache._store["fresh"][1] == "value"


def test_sweep_expired_with_nothing_expired_returns_zero():
    cache = TTLCache()
    cache.set("key", "value", ttl_seconds=1000)

    assert cache.sweep_expired() == 0
    assert cache.get("key") == "value"
