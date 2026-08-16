"""Pi-hole HTTP client for the Pi-hole plugin.

Targets the Pi-hole v6 REST API (the FTL-backed API shipped since Pi-hole
6.0, not the older `admin/api.php` PHP API). Auth is session-based: `POST
/api/auth` with the admin/app password returns a session id (`sid`) and a
CSRF token, both cached in-memory (see `storage/cache.py`) until the
session's `validity` window elapses or a 401 forces re-auth — the same
cache-until-401 shape `jellyfin_client` uses for its password auth mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.storage.cache import cache

# Safety margin below Pi-hole's reported session `validity` (default 1800s)
# so a request doesn't race a session that's about to expire server-side.
_SESSION_TTL_SAFETY_MARGIN_SECONDS = 60
_MIN_SESSION_TTL_SECONDS = 60

# Shared across every call/widget instance rather than one httpx.AsyncClient
# per request — every call here already carries its own full URL and
# stateless auth (sid query param / CSRF header), so one pooled client
# avoids paying a fresh TCP/TLS handshake on every poll (this plugin's
# default refresh_interval_seconds is 60s).
_client = httpx.AsyncClient(timeout=10)


class PiholeError(Exception):
    """Raised when a Pi-hole server can't be reached or rejects a request."""


@dataclass
class PiholeSession:
    sid: str
    csrf: str


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("host"))


def _base_url(settings: dict[str, Any]) -> str:
    scheme = "https" if settings.get("use_https") else "http"
    return f"{scheme}://{settings['host']}:{settings.get('port', 80)}"


async def _authenticate(base_url: str, widget_id: str, password: str) -> PiholeSession:
    try:
        response = await _client.post(f"{base_url}/api/auth", json={"password": password})
    except httpx.HTTPError as exc:
        raise PiholeError(f"Could not reach the Pi-hole server: {exc}") from exc

    if response.status_code == 401:
        raise PiholeError("Pi-hole rejected that password.")
    if response.status_code >= 400:
        raise PiholeError(f"Pi-hole login failed (HTTP {response.status_code}).")

    session = response.json().get("session") or {}
    if not session.get("valid"):
        raise PiholeError(session.get("message") or "Pi-hole rejected that password.")

    result = PiholeSession(sid=session["sid"], csrf=session.get("csrf", ""))
    ttl = max(int(session.get("validity", 1800)) - _SESSION_TTL_SAFETY_MARGIN_SECONDS, _MIN_SESSION_TTL_SECONDS)
    cache.set(f"pihole_sid:{widget_id}", result, ttl)
    return result


async def _resolve_session(settings: dict[str, Any], widget_id: str, *, force_reauth: bool = False) -> PiholeSession:
    cache_key = f"pihole_sid:{widget_id}"
    session = None if force_reauth else cache.get(cache_key)
    if session is None:
        base_url = _base_url(settings)
        session = await _authenticate(base_url, widget_id, settings.get("password") or "")
    return session


async def _request(
    method: str,
    path: str,
    *,
    settings: dict[str, Any],
    widget_id: str,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    base_url = _base_url(settings)
    session = await _resolve_session(settings, widget_id)

    async def send(session: PiholeSession) -> httpx.Response:
        query = {**(params or {}), "sid": session.sid}
        headers = {
            "X-FTL-SID": session.sid,
            "sid": session.sid,
        }
        if session.csrf:
            headers["X-FTL-CSRF"] = session.csrf
        return await _client.request(method, f"{base_url}{path}", params=query, headers=headers, json=json)

    try:
        response = await send(session)
    except httpx.HTTPError as exc:
        raise PiholeError(f"Could not reach the Pi-hole server: {exc}") from exc

    if response.status_code == 401:
        # The cached session expired/was revoked server-side — re-auth once
        # and retry, rather than surfacing a stale-session error.
        session = await _resolve_session(settings, widget_id, force_reauth=True)
        try:
            response = await send(session)
        except httpx.HTTPError as exc:
            raise PiholeError(f"Could not reach the Pi-hole server: {exc}") from exc

    if response.status_code >= 400:
        raise PiholeError(f"Pi-hole request failed (HTTP {response.status_code}).")
    return response


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    response = await _request("GET", "/api/info/version", settings=settings, widget_id=widget_id)
    core = (response.json().get("version") or {}).get("core") or {}
    local = core.get("local") or {}
    return local.get("version") or "Pi-hole"


async def get_summary_stats(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    response = await _request("GET", "/api/stats/summary", settings=settings, widget_id=widget_id)
    return response.json()


async def get_top_domains(
    settings: dict[str, Any], widget_id: str, *, blocked: bool, count: int = 5
) -> list[dict[str, Any]]:
    response = await _request(
        "GET",
        "/api/stats/top_domains",
        settings=settings,
        widget_id=widget_id,
        params={"blocked": str(blocked).lower(), "count": count},
    )
    domains = response.json().get("domains", [])
    return [{"domain": d["domain"], "count": d["count"]} for d in domains]


async def get_blocking_status(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    response = await _request("GET", "/api/dns/blocking", settings=settings, widget_id=widget_id)
    data = response.json()
    return {"blocking": data.get("blocking"), "timer": data.get("timer")}


async def set_blocking(
    settings: dict[str, Any], widget_id: str, enabled: bool, timer: int | None = None
) -> dict[str, Any]:
    response = await _request(
        "POST",
        "/api/dns/blocking",
        settings=settings,
        widget_id=widget_id,
        json={"blocking": enabled, "timer": timer},
    )
    data = response.json()
    return {"blocking": data.get("blocking"), "timer": data.get("timer")}
