from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import theme


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(theme.router)
    return TestClient(app)


def test_get_theme_lists_all_themes_with_dark_default(client):
    response = client.get("/api/theme")

    assert response.status_code == 200
    body = response.json()
    assert body["default"] == "dark"
    assert {t["id"] for t in body["themes"]} == {"light", "dark", "sepia", "contrast"}
