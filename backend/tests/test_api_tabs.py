from __future__ import annotations

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import tabs


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(tabs.router)
    return TestClient(app)


def test_list_tabs_defaults_when_unconfigured(client, tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text("widgets: []\n")
    monkeypatch.setattr("app.api.tabs.load_dashboard_config", lambda: yaml.safe_load(path.read_text()))

    response = client.get("/api/tabs")

    assert response.status_code == 200
    assert response.json() == [{"id": "default", "name": "Dashboard"}]


def test_list_tabs_returns_configured_tabs(client, tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
tabs:
  - id: home
    name: Home
  - id: media
    name: Media
widgets: []
"""
    )
    monkeypatch.setattr("app.api.tabs.load_dashboard_config", lambda: yaml.safe_load(path.read_text()))

    response = client.get("/api/tabs")

    assert response.status_code == 200
    assert response.json() == [{"id": "home", "name": "Home"}, {"id": "media", "name": "Media"}]
