"""Simple in-memory TTL cache for widget summary/detail data."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        """Drop every key starting with `prefix` — for invalidating cache
        entries fanned out across a dimension not known at delete time (e.g.
        one cached entry per device for a device-overridable setting)."""
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]

    def sweep_expired(self) -> int:
        """Actively drop every entry past its TTL, regardless of whether
        it's ever looked up again. `get()`'s lazy eviction alone leaves a
        high-cardinality, looked-up-once key (a flight callsign, a free-text
        geocode query) sitting in memory for the life of the process — this
        is what actually bounds that. Returns the number of keys dropped.
        """
        now = time.monotonic()
        expired = [key for key, (expires_at, _value) in self._store.items() if now > expires_at]
        for key in expired:
            del self._store[key]
        return len(expired)


cache = TTLCache()


async def cached_call(key: str, ttl_seconds: int, fetch: Callable[[], Awaitable[Any]]) -> Any:
    """Get-or-compute a single source call's result against the shared
    `cache` singleton.

    Distinct from the per-widget response cache applied in
    `app.api.widgets` (which is keyed by widget/user/device/locale and
    caches a whole get_summary()/get_detail() response): this caches one
    plugin-internal fetch, keyed by the call's own arguments, so it also
    naturally shares results across every widget/user/device requesting the
    same underlying source data — e.g. movies/plugin.py's per-item TMDB
    provider lookups, one of which can otherwise fan out to ~50 uncached
    calls per get_detail() invocation.
    """
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = await fetch()
    cache.set(key, value, ttl_seconds)
    return value


def user_locale_cache_key(user_id: str) -> str:
    """Shared key format for the cached-locale lookup in app.api.widgets —
    exposed here (rather than kept private to that module) so
    app.api.users' update_preferences can invalidate it by the same key on
    a locale change."""
    return f"user-locale:{user_id}"
