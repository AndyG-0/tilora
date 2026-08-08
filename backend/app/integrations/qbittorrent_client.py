"""qBittorrent WebUI API client for the qBittorrent plugin.

Auth is session-based, but unlike `pihole_client`/`synology_client` the
session is carried as a plain `SID` cookie rather than a query-param/header
token: `POST /api/v2/auth/login` (form-encoded `username`/`password`) sets
the cookie on success and replies with the literal body `"Ok."` — wrong
credentials still come back `200 OK` with body `"Fails."` rather than a 4xx,
so success has to be checked by reading the body, not the status code.
Authenticated requests that lack a valid `SID` cookie come back `403
Forbidden` (qBittorrent has no 401 for this API), which is treated as the
retry-once-after-reauth signal, mirroring the 401-triggers-reauth shape of
`pihole_client`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.storage.cache import cache

_SESSION_TTL_SECONDS = 1800


class QBittorrentError(Exception):
    """Raised when a qBittorrent server can't be reached or rejects a request."""


@dataclass
class QBittorrentSession:
    sid: str


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("host"))


def _base_url(settings: dict[str, Any]) -> str:
    scheme = "https" if settings.get("use_https") else "http"
    return f"{scheme}://{settings['host']}:{settings.get('port', 8080)}"


async def _authenticate(base_url: str, widget_id: str, username: str, password: str) -> QBittorrentSession:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                f"{base_url}/api/v2/auth/login",
                data={"username": username, "password": password},
                headers={"Referer": base_url},
            )
        except httpx.HTTPError as exc:
            raise QBittorrentError(f"Could not reach the qBittorrent server: {exc}") from exc

    if response.status_code == 403:
        raise QBittorrentError("qBittorrent has temporarily banned this IP after too many failed logins.")
    if response.status_code >= 400:
        raise QBittorrentError(f"qBittorrent login failed (HTTP {response.status_code}).")
    if response.text.strip() != "Ok.":
        raise QBittorrentError("qBittorrent rejected that username/password.")

    sid = response.cookies.get("SID")
    if not sid:
        raise QBittorrentError("qBittorrent login succeeded but returned no session cookie.")

    session = QBittorrentSession(sid=sid)
    cache.set(f"qbittorrent_sid:{widget_id}", session, _SESSION_TTL_SECONDS)
    return session


async def _resolve_session(
    settings: dict[str, Any], widget_id: str, *, force_reauth: bool = False
) -> QBittorrentSession:
    cache_key = f"qbittorrent_sid:{widget_id}"
    session = None if force_reauth else cache.get(cache_key)
    if session is None:
        base_url = _base_url(settings)
        session = await _authenticate(
            base_url, widget_id, settings.get("username") or "", settings.get("password") or ""
        )
    return session


async def _request(
    method: str,
    path: str,
    *,
    settings: dict[str, Any],
    widget_id: str,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    base_url = _base_url(settings)
    session = await _resolve_session(settings, widget_id)

    async def send(session: QBittorrentSession) -> httpx.Response:
        async with httpx.AsyncClient(timeout=10, cookies={"SID": session.sid}) as client:
            return await client.request(method, f"{base_url}{path}", params=params, headers={"Referer": base_url})

    try:
        response = await send(session)
    except httpx.HTTPError as exc:
        raise QBittorrentError(f"Could not reach the qBittorrent server: {exc}") from exc

    if response.status_code == 403:
        # The cached session expired/was revoked server-side — re-auth once
        # and retry, rather than surfacing a stale-session error.
        session = await _resolve_session(settings, widget_id, force_reauth=True)
        try:
            response = await send(session)
        except httpx.HTTPError as exc:
            raise QBittorrentError(f"Could not reach the qBittorrent server: {exc}") from exc

    if response.status_code >= 400:
        raise QBittorrentError(f"qBittorrent request failed (HTTP {response.status_code}).")
    return response


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    response = await _request("GET", "/api/v2/app/version", settings=settings, widget_id=widget_id)
    return response.text.strip().lstrip("v") or "qBittorrent"


async def get_maindata(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    response = await _request("GET", "/api/v2/sync/maindata", settings=settings, widget_id=widget_id, params={"rid": 0})
    return response.json()
