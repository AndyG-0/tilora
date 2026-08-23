from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import calendar_auth
from app.auth import get_current_admin
from app.config import settings
from app.storage import db

TOKEN_URL = "https://oauth2.googleapis.com/token"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def _state_from_redirect(location: str) -> str:
    return parse_qs(urlsplit(location).query)["state"][0]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(calendar_auth.router)
    # These tests exercise the OAuth flow, not auth — stub out who's asking
    # rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_admin] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


def test_start_auth_returns_400_when_client_not_configured(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", None)

    response = client.get("/api/calendar/auth/start", follow_redirects=False)

    assert response.status_code == 400


def test_start_auth_redirects_to_google(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", "client-id")

    response = client.get("/api/calendar/auth/start", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")


def test_start_auth_redirects_to_google_when_configured_via_settings_ui(client, tmp_db):
    db.save_app_settings({"google_calendar_client_id": "client-id"})

    response = client.get("/api/calendar/auth/start", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")


@respx.mock
def test_auth_callback_exchanges_code_and_redirects(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "client-secret")
    monkeypatch.setattr(settings, "cors_origin", "http://frontend.example")
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600})
    )
    start_response = client.get("/api/calendar/auth/start", follow_redirects=False)
    state = _state_from_redirect(start_response.headers["location"])

    response = client.get("/api/calendar/auth/callback", params={"code": "abc", "state": state}, follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://frontend.example/settings"
    assert db.get_oauth_tokens("google_calendar")["refresh_token"] == "r1"


def test_auth_callback_rejects_missing_state(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", "client-id")

    response = client.get("/api/calendar/auth/callback", params={"code": "abc"}, follow_redirects=False)

    assert response.status_code == 422


@respx.mock
def test_auth_callback_rejects_unknown_state_without_exchanging_code(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "client-secret")
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600})
    )

    response = client.get(
        "/api/calendar/auth/callback", params={"code": "abc", "state": "not-a-real-state"}, follow_redirects=False
    )

    assert response.status_code == 400
    assert route.call_count == 0
    assert db.get_oauth_tokens("google_calendar") is None


@respx.mock
def test_auth_callback_rejects_reused_state(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "client-secret")
    monkeypatch.setattr(settings, "cors_origin", "http://frontend.example")
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600})
    )
    start_response = client.get("/api/calendar/auth/start", follow_redirects=False)
    state = _state_from_redirect(start_response.headers["location"])
    first = client.get("/api/calendar/auth/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert first.status_code in (302, 307)

    replay = client.get("/api/calendar/auth/callback", params={"code": "abc", "state": state}, follow_redirects=False)

    assert replay.status_code == 400


def test_start_microsoft_auth_returns_400_when_client_not_configured(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "microsoft_calendar_client_id", None)

    response = client.get("/api/calendar/auth/microsoft/start", follow_redirects=False)

    assert response.status_code == 400


def test_start_microsoft_auth_redirects_to_microsoft(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "microsoft_calendar_client_id", "client-id")

    response = client.get("/api/calendar/auth/microsoft/start", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize")


def test_start_microsoft_auth_redirects_to_microsoft_when_configured_via_settings_ui(client, tmp_db):
    db.save_app_settings({"microsoft_calendar_client_id": "client-id"})

    response = client.get("/api/calendar/auth/microsoft/start", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize")


@respx.mock
def test_microsoft_auth_callback_exchanges_code_and_redirects(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "microsoft_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "microsoft_calendar_client_secret", "client-secret")
    monkeypatch.setattr(settings, "cors_origin", "http://frontend.example")
    respx.post(MICROSOFT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600})
    )
    start_response = client.get("/api/calendar/auth/microsoft/start", follow_redirects=False)
    state = _state_from_redirect(start_response.headers["location"])

    response = client.get(
        "/api/calendar/auth/microsoft/callback", params={"code": "abc", "state": state}, follow_redirects=False
    )

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://frontend.example/settings"
    assert db.get_oauth_tokens("microsoft_calendar")["refresh_token"] == "r1"


@respx.mock
def test_microsoft_auth_callback_rejects_unknown_state_without_exchanging_code(client, tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "microsoft_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "microsoft_calendar_client_secret", "client-secret")
    route = respx.post(MICROSOFT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600})
    )

    response = client.get(
        "/api/calendar/auth/microsoft/callback",
        params={"code": "abc", "state": "not-a-real-state"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert route.call_count == 0
    assert db.get_oauth_tokens("microsoft_calendar") is None


def test_status_reports_not_connected(client, tmp_db):
    response = client.get("/api/calendar/status")

    assert response.status_code == 200
    assert response.json() == {"connected": False}


def test_status_reports_connected(client, tmp_db):
    db.save_oauth_tokens("google_calendar", refresh_token="r1", access_token="a1")

    response = client.get("/api/calendar/status")

    assert response.json() == {"connected": True}


def test_calendar_routes_require_an_admin_session():
    app = FastAPI()
    app.include_router(calendar_auth.router)
    client = TestClient(app)

    assert client.get("/api/calendar/status").status_code == 401
