from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import theme
from app.auth import get_current_user


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(theme.router)
    # This test exercises the theme list, not auth — stub out who's asking
    # rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_user] = lambda: {"id": "user", "role": "member"}
    return TestClient(app)


def test_get_theme_lists_all_themes_with_dark_default(client):
    response = client.get("/api/theme")

    assert response.status_code == 200
    body = response.json()
    assert body["default"] == "dark"
    assert {t["id"] for t in body["themes"]} == {"light", "dark", "sepia", "contrast"}


def test_theme_route_requires_a_session():
    app = FastAPI()
    app.include_router(theme.router)
    client = TestClient(app)

    assert client.get("/api/theme").status_code == 401
