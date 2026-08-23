"""Microsoft identity platform OAuth 2.0 helpers for the calendar plugin's
BYO-credentials flow (Microsoft 365 / Outlook Calendar via Microsoft Graph).

Same authorization-code shape as `google_oauth.py`, confirmed against
Microsoft's own docs rather than assumed:

- Authorize/token endpoints and flow: confirmed against
  https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
  (fetched 2026-07-30). The `/common/` tenant segment (as opposed to
  `/organizations/` or `/consumers/`) accepts both personal Microsoft
  accounts and work/school accounts, which is what a personal dashboard app
  wants — the same reasoning Google's flow doesn't need since Google has no
  tenant concept. `response_mode=query` is the documented default for a
  `response_type=code` request and is passed explicitly for clarity.
- Scope: `Calendars.Read offline_access`. Unlike Google's `access_type=
  offline` query param, the v2.0 endpoint's docs state a `refresh_token` is
  only included in the token response "if `offline_access` scope was
  requested" — there's no separate access-type flag.
- Refresh token rotation: the same docs page's token-refresh section states
  the refresh response's `refresh_token` is "A new OAuth 2.0 refresh token.
  Replace the old refresh token with this newly acquired refresh token to
  ensure your refresh tokens remain valid for as long as possible" — i.e.
  Microsoft may rotate the refresh token on every refresh, unlike Google
  (which keeps the same refresh token indefinitely). `get_valid_access_token`
  below persists whatever refresh_token comes back (the new one if rotated,
  the same one otherwise) via `db.save_oauth_tokens`, not
  `db.save_oauth_access_token` (which only touches access_token/expires_at
  and would silently drop a rotated refresh token).
- Graph calendar read endpoint/shape: confirmed against
  https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview and
  https://learn.microsoft.com/en-us/graph/api/resources/event (fetched
  2026-07-30) — used by the calendar plugin, not this module.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import effective_settings, settings
from app.storage import db

_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_SCOPE = "https://graph.microsoft.com/Calendars.Read offline_access"
_PROVIDER = "microsoft_calendar"


def redirect_uri() -> str:
    return f"{settings.backend_public_url}/api/calendar/auth/microsoft/callback"


def build_auth_url() -> tuple[str, str]:
    """Returns (authorization_url, state) — the caller is responsible for
    persisting `state` and verifying it on the callback (CSRF protection)."""
    creds = effective_settings()
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": creds["microsoft_calendar_client_id"] or "",
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "response_mode": "query",
        "scope": _SCOPE,
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}", state


async def exchange_code(code: str) -> None:
    """Exchange an auth code for tokens and persist the refresh token."""
    creds = effective_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": creds["microsoft_calendar_client_id"] or "",
                "client_secret": creds["microsoft_calendar_client_secret"] or "",
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
                "scope": _SCOPE,
            },
        )
    response.raise_for_status()
    payload = response.json()
    expires_at = (datetime.now(UTC) + timedelta(seconds=payload["expires_in"])).isoformat()
    await asyncio.to_thread(
        db.save_oauth_tokens,
        _PROVIDER,
        refresh_token=payload["refresh_token"],
        access_token=payload["access_token"],
        expires_at=expires_at,
    )


async def _refresh_access_token(refresh_token: str) -> dict[str, Any]:
    creds = effective_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": creds["microsoft_calendar_client_id"] or "",
                "client_secret": creds["microsoft_calendar_client_secret"] or "",
                "grant_type": "refresh_token",
                "scope": _SCOPE,
            },
        )
    response.raise_for_status()
    return response.json()


def is_connected() -> bool:
    return db.get_oauth_tokens(_PROVIDER) is not None


async def get_valid_access_token() -> str | None:
    """The stored access token, refreshed first if it's expired or about to be.

    Unlike `google_oauth.get_valid_access_token`, the refresh path here
    persists via `db.save_oauth_tokens` (refresh_token + access_token +
    expires_at) rather than `db.save_oauth_access_token` (access_token +
    expires_at only), because Microsoft may rotate the refresh token on every
    refresh — see the module docstring. `payload.get("refresh_token")` falls
    back to the existing refresh token when Microsoft doesn't rotate it.
    """
    tokens = await asyncio.to_thread(db.get_oauth_tokens, _PROVIDER)
    if tokens is None:
        return None

    expires_at = tokens["expires_at"]
    if expires_at is not None and datetime.fromisoformat(expires_at) > datetime.now(UTC) + timedelta(minutes=1):
        return tokens["access_token"]

    payload = await _refresh_access_token(tokens["refresh_token"])
    new_expires_at = (datetime.now(UTC) + timedelta(seconds=payload["expires_in"])).isoformat()
    await asyncio.to_thread(
        db.save_oauth_tokens,
        _PROVIDER,
        refresh_token=payload.get("refresh_token") or tokens["refresh_token"],
        access_token=payload["access_token"],
        expires_at=new_expires_at,
    )
    return payload["access_token"]
