from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text("widgets: []\n")
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)
    return path


def test_health_endpoint_and_app_lifespan_boot_cleanly(tmp_db, dashboard_yaml):
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
