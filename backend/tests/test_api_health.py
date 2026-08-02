from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_and_app_lifespan_boot_cleanly(tmp_db):
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
