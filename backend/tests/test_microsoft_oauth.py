from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx

from app.config import settings
from app.integrations import microsoft_oauth
from app.storage import db

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "microsoft_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "microsoft_calendar_client_secret", "client-secret")
    monkeypatch.setattr(settings, "backend_public_url", "http://backend.example")


async def test_build_auth_url_includes_client_id_and_redirect_uri(tmp_db, monkeypatch):
    _configure(monkeypatch)

    url, state = await microsoft_oauth.build_auth_url()

    assert "client_id=client-id" in url
    assert "redirect_uri=http%3A%2F%2Fbackend.example%2Fapi%2Fcalendar%2Fauth%2Fmicrosoft%2Fcallback" in url
    assert f"state={state}" in url
    assert state


async def test_build_auth_url_generates_a_fresh_state_each_call(tmp_db, monkeypatch):
    _configure(monkeypatch)

    _, state1 = await microsoft_oauth.build_auth_url()
    _, state2 = await microsoft_oauth.build_auth_url()

    assert state1 != state2


def test_is_connected_false_when_no_tokens_stored(tmp_db):
    assert microsoft_oauth.is_connected() is False


@respx.mock
async def test_exchange_code_persists_tokens(tmp_db, monkeypatch):
    _configure(monkeypatch)
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600},
        )
    )

    await microsoft_oauth.exchange_code("auth-code")

    assert microsoft_oauth.is_connected() is True
    tokens = db.get_oauth_tokens("microsoft_calendar")
    assert tokens["refresh_token"] == "r1"
    assert tokens["access_token"] == "a1"


async def test_get_valid_access_token_returns_none_when_not_connected(tmp_db):
    assert await microsoft_oauth.get_valid_access_token() is None


async def test_get_valid_access_token_returns_cached_token_when_not_expired(tmp_db):
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    db.save_oauth_tokens("microsoft_calendar", refresh_token="r1", access_token="a1", expires_at=future)

    token = await microsoft_oauth.get_valid_access_token()

    assert token == "a1"


@respx.mock
async def test_get_valid_access_token_refreshes_when_expired(tmp_db, monkeypatch):
    _configure(monkeypatch)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    db.save_oauth_tokens("microsoft_calendar", refresh_token="r1", access_token="stale", expires_at=past)
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600}))

    token = await microsoft_oauth.get_valid_access_token()

    assert token == "fresh"
    assert db.get_oauth_tokens("microsoft_calendar")["refresh_token"] == "r1"


@respx.mock
async def test_get_valid_access_token_persists_rotated_refresh_token(tmp_db, monkeypatch):
    """Microsoft may return a new refresh_token on refresh (token rotation),
    unlike Google. The rotated value must be persisted, or the next refresh
    would be attempted with a discarded, possibly-invalidated token."""
    _configure(monkeypatch)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    db.save_oauth_tokens("microsoft_calendar", refresh_token="r1", access_token="stale", expires_at=past)
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "fresh", "refresh_token": "r2-rotated", "expires_in": 3600}
        )
    )

    token = await microsoft_oauth.get_valid_access_token()

    assert token == "fresh"
    assert db.get_oauth_tokens("microsoft_calendar")["refresh_token"] == "r2-rotated"
