"""Google OAuth 2.0 helpers for the calendar plugin's BYO-credentials flow.

Authorization-code flow: the user is redirected to Google's consent screen,
Google redirects back to our callback with a `code`, we exchange that for an
access + refresh token pair and persist the refresh token. Access tokens are
short-lived and refreshed on demand via `get_valid_access_token`.
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

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
_PROVIDER = "google_calendar"


def redirect_uri() -> str:
    return f"{settings.backend_public_url}/api/calendar/auth/callback"


async def build_auth_url() -> tuple[str, str]:
    """Returns (authorization_url, state) — the caller is responsible for
    persisting `state` and verifying it on the callback (CSRF protection)."""
    creds = await effective_settings()
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": creds["google_calendar_client_id"] or "",
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}", state


async def exchange_code(code: str) -> None:
    """Exchange an auth code for tokens and persist the refresh token."""
    creds = await effective_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": creds["google_calendar_client_id"] or "",
                "client_secret": creds["google_calendar_client_secret"] or "",
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
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
    creds = await effective_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": creds["google_calendar_client_id"] or "",
                "client_secret": creds["google_calendar_client_secret"] or "",
                "grant_type": "refresh_token",
            },
        )
    response.raise_for_status()
    return response.json()


def is_connected() -> bool:
    return db.get_oauth_tokens(_PROVIDER) is not None


async def get_valid_access_token() -> str | None:
    """The stored access token, refreshed first if it's expired or about to be."""
    tokens = await asyncio.to_thread(db.get_oauth_tokens, _PROVIDER)
    if tokens is None:
        return None

    expires_at = tokens["expires_at"]
    if expires_at is not None and datetime.fromisoformat(expires_at) > datetime.now(UTC) + timedelta(minutes=1):
        return tokens["access_token"]

    payload = await _refresh_access_token(tokens["refresh_token"])
    new_expires_at = (datetime.now(UTC) + timedelta(seconds=payload["expires_in"])).isoformat()
    await asyncio.to_thread(db.save_oauth_access_token, _PROVIDER, payload["access_token"], new_expires_at)
    return payload["access_token"]
