from __future__ import annotations

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import devices as devices_api
from app.api import users as users_api
from app.api import widgets as widgets_api


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(devices_api.router)
    app.include_router(users_api.router)
    app.include_router(widgets_api.router)
    return TestClient(app)


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
widgets:
  - id: clock
    type: clock
    enabled: true
    layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
"""
    )
    monkeypatch.setattr("app.api.widgets.load_dashboard_config", lambda: yaml.safe_load(path.read_text()))
    return path


def test_full_register_login_layout_switch_profile_flow(client, dashboard_yaml, tmp_db):
    # 1. First launch on a fresh browser: register the device.
    register = client.post("/api/devices/register")
    assert register.json()["is_new"] is True

    # 2. Profile picker is empty on a fresh install — no profile is seeded.
    profiles = client.get("/api/users").json()
    assert profiles == []

    # 3. Create two real profiles.
    alice = client.post("/api/users", json={"name": "Alice"}).json()
    client.post("/api/users/logout")
    bob = client.post("/api/users", json={"name": "Bob"}).json()
    client.post("/api/users/logout")

    # 4. Alice logs in on this device and drags a widget.
    client.post(f"/api/users/{alice['id']}/login", json={})
    client.put(
        "/api/widgets/layout",
        json={
            "breakpoint": "wide",
            "widgets": [{"id": "clock", "layout": {"col": 3, "row": 3, "colSpan": 1, "rowSpan": 1}}],
        },
    )
    alice_widgets = client.get("/api/widgets?breakpoint=wide").json()
    assert alice_widgets[0]["layout"] == {"col": 3, "row": 3, "colSpan": 1, "rowSpan": 1}

    # 5. Bob logs in on the same device — his layout is untouched (still the
    # dashboard.yaml default), confirming per-user scoping.
    client.post("/api/users/logout")
    client.post(f"/api/users/{bob['id']}/login", json={})
    bob_widgets = client.get("/api/widgets?breakpoint=wide").json()
    assert bob_widgets[0]["layout"] == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}

    # 6. Switching back to Alice on this device shows her drag again.
    client.post("/api/users/logout")
    client.post(f"/api/users/{alice['id']}/login", json={})
    alice_widgets_again = client.get("/api/widgets?breakpoint=wide").json()
    assert alice_widgets_again[0]["layout"] == {"col": 3, "row": 3, "colSpan": 1, "rowSpan": 1}


def test_layout_is_scoped_per_user_and_device_pair(client, dashboard_yaml, tmp_db):
    # Layout is keyed by (user, device, breakpoint) — a drag on one screen
    # must not silently show up (or be overwritten) on another screen the
    # same user is logged into elsewhere, since two screens may want
    # independent arrangements.
    client.post("/api/devices/register")
    alice = client.post("/api/users", json={"name": "Alice"}).json()

    client.put(
        "/api/widgets/layout",
        json={
            "breakpoint": "wide",
            "widgets": [{"id": "clock", "layout": {"col": 3, "row": 3, "colSpan": 1, "rowSpan": 1}}],
        },
    )

    # A second device, same user: fresh cookie jar, log in again.
    other_client = TestClient(client.app)
    other_client.post("/api/devices/register")
    other_client.post(f"/api/users/{alice['id']}/login", json={})

    other_widgets = other_client.get("/api/widgets?breakpoint=wide").json()
    assert other_widgets[0]["layout"] == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}


def test_widgets_endpoints_require_both_device_and_user_auth(client, dashboard_yaml, tmp_db):
    assert client.get("/api/widgets?breakpoint=wide").status_code == 401

    client.post("/api/devices/register")
    assert client.get("/api/widgets?breakpoint=wide").status_code == 401

    profile = client.post("/api/users", json={"name": "Alice"}).json()
    client.post(f"/api/users/{profile['id']}/login", json={})
    assert client.get("/api/widgets?breakpoint=wide").status_code == 200
