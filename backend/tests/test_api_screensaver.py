from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import screensaver as screensaver_api
from app.storage import db

_DEFAULTS = {
    "enabled": False,
    "idle_timeout_seconds": 300,
    "rotation_interval_seconds": 25,
    "widget_ids": [],
    "text_animation_style": "marquee",
    "led_color": "#ff8a00",
    "text_pause_seconds": 8,
    "flipboard_pattern": "top_to_bottom",
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(screensaver_api.router)
    return TestClient(app)


def _login(client, user_id="alice", device_id="tablet"):
    db.create_user(user_id, "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_device(device_id, "Tablet", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    db.create_session("sess1", user_id, device_id, "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess1")
    client.cookies.set("tilora_device", device_id)


def test_get_settings_requires_a_user_session(client, tmp_db):
    response = client.get("/api/screensaver/settings")

    assert response.status_code == 401


def test_get_settings_returns_defaults_when_unset(client, tmp_db):
    _login(client)

    response = client.get("/api/screensaver/settings")

    assert response.status_code == 200
    assert response.json() == _DEFAULTS


def test_patch_settings_persists_a_partial_update(client, tmp_db):
    _login(client)

    response = client.patch(
        "/api/screensaver/settings",
        json={"enabled": True, "idle_timeout_seconds": 60, "widget_ids": ["clock", "discord"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "idle_timeout_seconds": 60,
        "rotation_interval_seconds": 25,
        "widget_ids": ["clock", "discord"],
        "text_animation_style": "marquee",
        "led_color": "#ff8a00",
        "text_pause_seconds": 8,
        "flipboard_pattern": "top_to_bottom",
    }
    assert client.get("/api/screensaver/settings").json()["enabled"] is True


def test_patch_settings_merges_onto_prior_values(client, tmp_db):
    _login(client)
    client.patch("/api/screensaver/settings", json={"enabled": True, "widget_ids": ["clock"]})

    response = client.patch("/api/screensaver/settings", json={"rotation_interval_seconds": 10})

    assert response.json() == {
        "enabled": True,
        "idle_timeout_seconds": 300,
        "rotation_interval_seconds": 10,
        "widget_ids": ["clock"],
        "text_animation_style": "marquee",
        "led_color": "#ff8a00",
        "text_pause_seconds": 8,
        "flipboard_pattern": "top_to_bottom",
    }


def test_patch_settings_updates_text_animation_style(client, tmp_db):
    _login(client)

    response = client.patch("/api/screensaver/settings", json={"text_animation_style": "matrix"})

    assert response.status_code == 200
    assert response.json()["text_animation_style"] == "matrix"


def test_patch_settings_rejects_invalid_text_animation_style(client, tmp_db):
    _login(client)

    response = client.patch("/api/screensaver/settings", json={"text_animation_style": "bogus"})

    assert response.status_code == 422


def test_patch_settings_updates_led_color(client, tmp_db):
    _login(client)

    response = client.patch("/api/screensaver/settings", json={"led_color": "#00ff00"})

    assert response.status_code == 200
    assert response.json()["led_color"] == "#00ff00"


def test_patch_settings_updates_text_pause_seconds(client, tmp_db):
    _login(client)

    response = client.patch("/api/screensaver/settings", json={"text_pause_seconds": 12})

    assert response.status_code == 200
    assert response.json()["text_pause_seconds"] == 12


def test_patch_settings_updates_flipboard_pattern(client, tmp_db):
    _login(client)

    response = client.patch("/api/screensaver/settings", json={"flipboard_pattern": "random"})

    assert response.status_code == 200
    assert response.json()["flipboard_pattern"] == "random"


def test_patch_settings_rejects_invalid_flipboard_pattern(client, tmp_db):
    _login(client)

    response = client.patch("/api/screensaver/settings", json={"flipboard_pattern": "bogus"})

    assert response.status_code == 422


def test_settings_are_scoped_independently_per_device_for_the_same_user(client, tmp_db):
    _login(client, user_id="alice", device_id="tablet")
    client.patch("/api/screensaver/settings", json={"enabled": True})

    db.create_device("phone", "Phone", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    client.cookies.set("tilora_device", "phone")

    assert client.get("/api/screensaver/settings").json()["enabled"] is False


def test_settings_are_scoped_independently_per_user_for_the_same_device(client, tmp_db):
    _login(client, user_id="alice", device_id="tablet")
    client.patch("/api/screensaver/settings", json={"enabled": True})

    db.create_user("bob", "Bob", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_session("sess2", "bob", "tablet", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess2")

    assert client.get("/api/screensaver/settings").json()["enabled"] is False
