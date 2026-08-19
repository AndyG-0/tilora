from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import reports
from app.auth import get_current_device, get_current_user
from app.storage import db

TEST_USER_ID = "test-user-1"
TEST_DEVICE_ID = "test-device-1"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(reports.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "name": "Test User", "role": "admin"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID, "name": "Test Device"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(reports.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "name": "Test User", "role": "member"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID, "name": "Test Device"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(reports.router)
    return TestClient(app)


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
widgets:
  - id: weather
    type: weather
    layout:
      col: 1
      row: 1
      colSpan: 2
      rowSpan: 2
    tab: home
  - id: date
    type: date
    layout:
      col: 3
      row: 1
      colSpan: 1
      rowSpan: 1
    tab: home
tabs:
  - id: home
    name: Home
  - id: media
    name: Media
"""
    )
    monkeypatch.setattr("app.config.DASHBOARD_CONFIG_PATH", path)
    return path


def test_reports_requires_auth(unauthenticated_client):
    response = unauthenticated_client.get("/api/reports/tiles")
    assert response.status_code == 401


def test_get_tiles_report_empty_custom(tmp_db, dashboard_yaml, client):
    response = client.get("/api/reports/tiles")
    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert "tiles" in data
    assert data["summary"]["total_tiles"] == 2
    assert data["summary"]["builtin_tiles"] == 2
    assert data["summary"]["custom_tiles"] == 0
    assert data["summary"]["custom_named_tiles"] == 0
    assert data["summary"]["tabs_count"] == 2

    weather_tile = next(t for t in data["tiles"] if t["id"] == "weather")
    assert weather_tile["type"] == "weather"
    assert weather_tile["source"] == "builtin"
    assert weather_tile["has_custom_name"] is False
    assert weather_tile["custom_name"] is None
    assert weather_tile["size_description"] == "Standard (2 × 2)"
    assert weather_tile["tab_id"] == "home"
    assert weather_tile["tab_name"] == "Home"
    assert weather_tile["is_hidden"] is False


def test_get_tiles_report_with_custom_widget_and_custom_name(tmp_db, dashboard_yaml, client):
    # Add a user and device
    db.create_user(TEST_USER_ID, "Alice", None, "pin_hash", "pin_salt", 1000, "2026-01-01T00:00:00")
    db.create_device(TEST_DEVICE_ID, "Living Room Tablet", "2026-01-01T00:00:00", "2026-01-01T00:00:00")

    # Add custom widget
    db.save_custom_widget(
        "chores-custom-1",
        "chores",
        {"col": 1, "row": 2, "colSpan": 4, "rowSpan": 1},
        "home",
        TEST_USER_ID,
        TEST_DEVICE_ID,
    )
    # Set custom name
    db.save_widget_custom_name("chores-custom-1", "Family Chores")
    db.save_widget_custom_name("weather", "City Weather")

    # Add some chores in DB
    db.add_chore("chores-custom-1", TEST_USER_ID, "Clean Kitchen")
    db.add_chore("chores-custom-1", TEST_USER_ID, "Take Out Trash")

    response = client.get("/api/reports/tiles")
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["total_tiles"] == 3
    assert data["summary"]["builtin_tiles"] == 2
    assert data["summary"]["custom_tiles"] == 1
    assert data["summary"]["custom_named_tiles"] == 2

    chores_tile = next(t for t in data["tiles"] if t["id"] == "chores-custom-1")
    assert chores_tile["source"] == "custom"
    assert chores_tile["has_custom_name"] is True
    assert chores_tile["custom_name"] == "Family Chores"
    assert chores_tile["size_description"] == "Banner (4 × 1)"
    assert chores_tile["owner_user_id"] == TEST_USER_ID
    assert chores_tile["owner_user_name"] == "Alice"
    assert chores_tile["owner_device_id"] == TEST_DEVICE_ID
    assert chores_tile["owner_device_name"] == "Living Room Tablet"
    assert chores_tile["stats"]["chores_active"] == 2
    assert chores_tile["stats"]["chores_total"] == 2

    weather_tile = next(t for t in data["tiles"] if t["id"] == "weather")
    assert weather_tile["has_custom_name"] is True
    assert weather_tile["custom_name"] == "City Weather"


def test_get_tiles_report_reflects_hidden_status(tmp_db, dashboard_yaml, client):
    db.hide_widget(TEST_USER_ID, TEST_DEVICE_ID, "weather")

    response = client.get("/api/reports/tiles")
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["hidden_tiles"] == 1
    weather_tile = next(t for t in data["tiles"] if t["id"] == "weather")
    assert weather_tile["is_hidden"] is True


def test_get_tiles_report_with_photos_property_scope(tmp_db, tmp_path, monkeypatch, client):
    path = tmp_path / "dashboard_photos.yaml"
    path.write_text(
        """
widgets:
  - id: photos
    type: photos
    layout:
      col: 1
      row: 1
      colSpan: 2
      rowSpan: 2
    tab: home
tabs:
  - id: home
    name: Home
"""
    )
    monkeypatch.setattr("app.config.DASHBOARD_CONFIG_PATH", path)

    response = client.get("/api/reports/tiles")
    assert response.status_code == 200
    data = response.json()

    photos_tile = next(t for t in data["tiles"] if t["id"] == "photos")
    assert photos_tile["type"] == "photos"
    assert photos_tile["settings_scope"] in ("network", "personal")
    assert isinstance(photos_tile["settings_scope"], str)


def test_get_tiles_report_scopes_out_other_users_tiles_for_member(tmp_db, dashboard_yaml, member_client):
    other_user_id = "test-user-2"
    other_device_id = "test-device-2"
    db.create_user(TEST_USER_ID, "Alice", None, "pin_hash", "pin_salt", 1000, "2026-01-01T00:00:00")
    db.create_user(other_user_id, "Bob", None, "pin_hash", "pin_salt", 1000, "2026-01-01T00:00:00")
    db.create_device(TEST_DEVICE_ID, "Alice's Tablet", "2026-01-01T00:00:00", "2026-01-01T00:00:00")
    db.create_device(other_device_id, "Bob's Tablet", "2026-01-01T00:00:00", "2026-01-01T00:00:00")

    db.save_custom_widget(
        "chores-mine", "chores", {"col": 1, "row": 2, "colSpan": 4, "rowSpan": 1}, "home", TEST_USER_ID, TEST_DEVICE_ID
    )
    db.save_custom_widget(
        "chores-bobs",
        "chores",
        {"col": 1, "row": 3, "colSpan": 4, "rowSpan": 1},
        "home",
        other_user_id,
        other_device_id,
    )

    response = member_client.get("/api/reports/tiles")
    assert response.status_code == 200
    data = response.json()

    tile_ids = {t["id"] for t in data["tiles"]}
    assert "chores-mine" in tile_ids
    assert "chores-bobs" not in tile_ids
    # Unowned builtins from dashboard.yaml remain visible.
    assert "weather" in tile_ids
    assert "date" in tile_ids

    # Summary counts reflect only the scoped subset, not the full system.
    assert data["summary"]["total_tiles"] == 3
    assert data["summary"]["custom_tiles"] == 1


def test_get_tiles_report_admin_sees_all_owners(tmp_db, dashboard_yaml, client):
    other_user_id = "test-user-2"
    other_device_id = "test-device-2"
    db.create_user(TEST_USER_ID, "Alice", None, "pin_hash", "pin_salt", 1000, "2026-01-01T00:00:00")
    db.create_user(other_user_id, "Bob", None, "pin_hash", "pin_salt", 1000, "2026-01-01T00:00:00")
    db.create_device(TEST_DEVICE_ID, "Alice's Tablet", "2026-01-01T00:00:00", "2026-01-01T00:00:00")
    db.create_device(other_device_id, "Bob's Tablet", "2026-01-01T00:00:00", "2026-01-01T00:00:00")

    db.save_custom_widget(
        "chores-mine", "chores", {"col": 1, "row": 2, "colSpan": 4, "rowSpan": 1}, "home", TEST_USER_ID, TEST_DEVICE_ID
    )
    db.save_custom_widget(
        "chores-bobs",
        "chores",
        {"col": 1, "row": 3, "colSpan": 4, "rowSpan": 1},
        "home",
        other_user_id,
        other_device_id,
    )

    response = client.get("/api/reports/tiles")
    assert response.status_code == 200
    data = response.json()

    tile_ids = {t["id"] for t in data["tiles"]}
    assert "chores-mine" in tile_ids
    assert "chores-bobs" in tile_ids
    assert data["summary"]["total_tiles"] == 4
    assert data["summary"]["custom_tiles"] == 2
