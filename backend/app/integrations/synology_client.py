"""Synology DSM Web API client for the Synology plugin.

Auth is session-based, same shape as `pihole_client`: `GET
/webapi/auth.cgi?api=SYNO.API.Auth&method=login&...` returns a session id
(`sid`), cached in-memory (see `storage/cache.py`) and appended to every
subsequent request as the `_sid` query parameter until a request comes back
unauthorized, at which point one re-auth-and-retry happens.

Two read-only data calls, both part of DSM's stable, publicly documented Web
API surface:
- `SYNO.Storage.CGI.Storage` (method=`load_info`): per-volume total/used
  bytes and health status.
- `SYNO.Core.System` (method=`info`): model name, uptime, and CPU
  temperature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.storage.cache import cache

_SESSION_TTL_SECONDS = 1800
_SESSION_APP = "Tilora"

# DSM error codes common to every Web API endpoint (from the "Common Error
# Codes" table in Synology's Web API guide).
_COMMON_ERRORS = {
    100: "unknown error",
    101: "invalid parameter",
    102: "the requested API does not exist",
    103: "the requested method does not exist",
    104: "the requested API version is not supported",
    105: "permission denied — this DSM account doesn't have access to that API",
    106: "session timed out",
    107: "session interrupted by a duplicate login",
    119: "invalid or expired session",
}

# DSM error codes specific to SYNO.API.Auth/login.
_AUTH_ERRORS = {
    400: "no such account exists, or the password is incorrect",
    401: "this DSM account is disabled",
    402: "permission denied for this DSM account",
    403: "this DSM account requires a 2-factor authentication code, which isn't supported here",
    404: "the 2-factor authentication code was incorrect",
}

# Session-related codes where a stale/expired sid is the likely cause and a
# reauth-and-retry can plausibly fix it; anything else (e.g. permission
# denied) won't be fixed by re-authenticating, so don't waste a retry on it.
_RETRYABLE_CODES = {106, 119}

# How long to trust a discovered API version before re-checking it.
_API_VERSION_TTL_SECONDS = 86400


def _error_message(body: dict[str, Any], table: dict[int, str], fallback: str) -> str:
    code = body.get("error", {}).get("code")
    if code in table:
        return f"{fallback}: {table[code]} (DSM error {code})."
    if code is not None:
        return f"{fallback} (DSM error {code})."
    return f"{fallback}."


class SynologyError(Exception):
    """Raised when a Synology DSM server can't be reached or rejects a request."""


@dataclass
class SynologySession:
    sid: str


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("host")) and bool(settings.get("username")) and bool(settings.get("password"))


def _base_url(settings: dict[str, Any]) -> str:
    scheme = "https" if settings.get("use_https") else "http"
    return f"{scheme}://{settings['host']}:{settings.get('port', 5000)}"


async def _authenticate(base_url: str, widget_id: str, username: str, password: str) -> SynologySession:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(
                f"{base_url}/webapi/auth.cgi",
                params={
                    "api": "SYNO.API.Auth",
                    "version": 6,
                    "method": "login",
                    "account": username,
                    "passwd": password,
                    "session": _SESSION_APP,
                    "format": "sid",
                },
            )
        except httpx.HTTPError as exc:
            raise SynologyError(f"Could not reach the Synology NAS: {exc}") from exc

    if response.status_code >= 400:
        raise SynologyError(f"Synology login failed (HTTP {response.status_code}).")

    body = response.json()
    if not body.get("success"):
        raise SynologyError(_error_message(body, _AUTH_ERRORS, "Synology login failed"))

    session = SynologySession(sid=body["data"]["sid"])
    cache.set(f"synology_sid:{widget_id}", session, _SESSION_TTL_SECONDS)
    return session


async def _resolve_session(settings: dict[str, Any], widget_id: str, *, force_reauth: bool = False) -> SynologySession:
    cache_key = f"synology_sid:{widget_id}"
    session = None if force_reauth else cache.get(cache_key)
    if session is None:
        base_url = _base_url(settings)
        session = await _authenticate(
            base_url, widget_id, settings.get("username") or "", settings.get("password") or ""
        )
    return session


async def _discover_version(base_url: str, api: str, fallback: int, widget_id: str) -> int:
    """Look up the API version DSM actually supports for `api`.

    Different DSM releases support different min/max versions per API, and
    calling with an unsupported version comes back as `success: false` with
    error 103 ("the requested method does not exist") rather than anything
    that names the version as the problem — a hardcoded version is
    effectively a guess. `SYNO.API.Info`/`query` is DSM's own unauthenticated
    directory of what each API supports, so ask it and use the max version
    it reports instead of guessing. Any failure here (network, unexpected
    shape, mocked-away in tests) just falls back to the caller's default —
    this is a best-effort optimization, not something that should block the
    real request.
    """
    cache_key = f"synology_api_version:{widget_id}:{api}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{base_url}/webapi/query.cgi",
                params={"api": "SYNO.API.Info", "version": 1, "method": "query", "query": api},
            )
        body = response.json()
        max_version = body["data"][api]["maxVersion"]
        if not isinstance(max_version, int):
            return fallback
    except Exception:
        return fallback
    cache.set(cache_key, max_version, _API_VERSION_TTL_SECONDS)
    return max_version


async def _request(
    api: str,
    method: str,
    *,
    version: int,
    settings: dict[str, Any],
    widget_id: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url = _base_url(settings)
    session = await _resolve_session(settings, widget_id)
    version = await _discover_version(base_url, api, version, widget_id)

    async def send(session: SynologySession) -> httpx.Response:
        query = {"api": api, "version": version, "method": method, "_sid": session.sid, **(params or {})}
        async with httpx.AsyncClient(timeout=10) as client:
            return await client.get(f"{base_url}/webapi/entry.cgi", params=query)

    try:
        response = await send(session)
    except httpx.HTTPError as exc:
        raise SynologyError(f"Could not reach the Synology NAS: {exc}") from exc

    body = response.json() if response.status_code < 400 else {}

    def _is_retryable() -> bool:
        if response.status_code >= 400:
            return True
        return body.get("error", {}).get("code") in _RETRYABLE_CODES

    if not body.get("success") and _is_retryable():
        # An expired/revoked session comes back as a 200 with success: false
        # (error code 106/119) rather than an HTTP 401, so treat that
        # specific signal as a stale session and re-auth once and retry.
        # Other failure codes (e.g. 105 permission denied) won't be fixed by
        # re-authenticating, so those raise immediately below instead.
        session = await _resolve_session(settings, widget_id, force_reauth=True)
        try:
            response = await send(session)
        except httpx.HTTPError as exc:
            raise SynologyError(f"Could not reach the Synology NAS: {exc}") from exc
        body = response.json() if response.status_code < 400 else {}

    if response.status_code >= 400:
        raise SynologyError(f"Synology API request failed (HTTP {response.status_code}).")
    if not body.get("success"):
        raise SynologyError(_error_message(body, _COMMON_ERRORS, "Synology API request failed"))

    return body["data"]


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    data = await _request("SYNO.Core.System", "info", version=1, settings=settings, widget_id=widget_id)
    return data.get("model") or "Synology NAS"


async def get_storage(settings: dict[str, Any], widget_id: str) -> list[dict[str, Any]]:
    data = await _request("SYNO.Storage.CGI.Storage", "load_info", version=1, settings=settings, widget_id=widget_id)
    volumes = data.get("volumes") or []
    result = []
    for volume in volumes:
        size = volume.get("size") or {}
        total = int(size.get("total", 0))
        used = int(size.get("used", 0))
        result.append(
            {
                "name": volume.get("desc") or volume.get("id") or "Volume",
                "total_bytes": total,
                "used_bytes": used,
                "used_percent": round((used / total) * 100, 1) if total else 0,
                "status": volume.get("status") or "unknown",
            }
        )
    return result


async def get_system_info(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    data = await _request("SYNO.Core.System", "info", version=1, settings=settings, widget_id=widget_id)
    return {
        "model": data.get("model"),
        "uptime": data.get("up_time"),
        "temperature_celsius": data.get("temperature"),
    }
