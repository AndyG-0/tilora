from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.plugins.base import registry
from app.plugins.weather.plugin import WeatherPlugin


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
widgets:
  - id: weather
    type: weather
    enabled: true
    layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
    settings: { latitude: 1, longitude: 2 }
  - id: disabled-widget
    type: weather
    enabled: false
    layout: { col: 2, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
"""
    )
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)
    return path


def test_load_plugins_registers_enabled_widgets_and_skips_disabled(dashboard_yaml, tmp_db):
    main.load_plugins()

    assert isinstance(registry.get("weather"), WeatherPlugin)
    assert registry.get("disabled-widget") is None


def test_load_plugins_raises_for_unregistered_widget_type(tmp_path, tmp_db, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
widgets:
  - id: mystery
    type: not_a_real_plugin_type
    enabled: true
    layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
"""
    )
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)

    with pytest.raises(ValueError, match="not_a_real_plugin_type"):
        main.load_plugins()


def test_load_plugins_layers_db_persisted_settings_over_yaml(dashboard_yaml, tmp_db):
    from app.storage import db

    db.save_widget_settings("weather", {"latitude": 99})

    main.load_plugins()

    weather = registry.get("weather")
    assert weather.config["settings"]["latitude"] == 99
    assert weather.config["settings"]["longitude"] == 2


def test_cors_middleware_allows_lan_origin():
    client = TestClient(main.app)
    response = client.get("/api/health", headers={"Origin": "http://192.168.1.123:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://192.168.1.123:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_request_logging_levels(caplog):
    import logging

    client = TestClient(main.app)

    # Routine GET request should log at DEBUG level
    with caplog.at_level(logging.DEBUG, logger="app.main"):
        caplog.clear()
        res = client.get("/api/health")
        assert res.status_code == 200
        get_records = [r for r in caplog.records if r.name == "app.main" and "GET /api/health" in r.message]
        assert len(get_records) == 1
        assert get_records[0].levelno == logging.DEBUG

    # 404 error request should log at INFO level
    with caplog.at_level(logging.INFO, logger="app.main"):
        caplog.clear()
        res = client.get("/api/nonexistent-endpoint-test")
        assert res.status_code == 404
        error_records = [
            r for r in caplog.records if r.name == "app.main" and "/api/nonexistent-endpoint-test" in r.message
        ]
        assert len(error_records) == 1
        assert error_records[0].levelno == logging.INFO
