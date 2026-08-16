from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import devices as devices_api
from app.auth import DEVICE_COOKIE_NAME
from app.storage import db


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(devices_api.router)
    return TestClient(app)


def test_register_creates_a_new_device_and_sets_a_cookie(client, tmp_db):
    response = client.post("/api/devices/register")

    assert response.status_code == 200
    body = response.json()
    assert body["is_new"] is True
    assert body["name"] == "New Device"
    assert DEVICE_COOKIE_NAME in response.cookies


def test_register_is_idempotent_for_an_existing_valid_device_cookie(client, tmp_db):
    first = client.post("/api/devices/register").json()

    second = client.post("/api/devices/register")

    assert second.status_code == 200
    body = second.json()
    assert body["is_new"] is False
    assert body["id"] == first["id"]


def test_me_requires_a_device_cookie(client, tmp_db):
    response = client.get("/api/devices/me")

    assert response.status_code == 401


def test_me_returns_the_registered_device(client, tmp_db):
    client.post("/api/devices/register")

    response = client.get("/api/devices/me")

    assert response.status_code == 200
    assert response.json()["name"] == "New Device"


def test_register_creates_unique_default_names_when_collisions_exist(client, tmp_db):
    first = client.post("/api/devices/register").json()
    assert first["name"] == "New Device"

    client.cookies.clear()
    second = client.post("/api/devices/register").json()
    assert second["name"] == "New Device 2"

    client.cookies.clear()
    third = client.post("/api/devices/register").json()
    assert third["name"] == "New Device 3"


def test_patch_me_renames_the_device(client, tmp_db):
    client.post("/api/devices/register")

    response = client.patch("/api/devices/me", json={"name": "Kitchen Tablet"})

    assert response.status_code == 200
    assert response.json()["name"] == "Kitchen Tablet"
    assert client.get("/api/devices/me").json()["name"] == "Kitchen Tablet"


def test_patch_me_refuses_empty_or_whitespace_name(client, tmp_db):
    client.post("/api/devices/register")

    response = client.patch("/api/devices/me", json={"name": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_patch_me_refuses_duplicate_name_case_insensitive(client, tmp_db):
    db.create_device("dev2", "Living Room TV", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    client.post("/api/devices/register")

    response = client.patch("/api/devices/me", json={"name": "living room tv"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_patch_me_allows_same_name_case_change_on_same_device(client, tmp_db):
    client.post("/api/devices/register")
    client.patch("/api/devices/me", json={"name": "Living Room TV"})

    response = client.patch("/api/devices/me", json={"name": "living room tv"})
    assert response.status_code == 200
    assert response.json()["name"] == "living room tv"


def test_list_all_devices_requires_a_user_session(client, tmp_db):
    response = client.get("/api/devices")

    assert response.status_code == 401


def test_list_all_devices_returns_every_registered_device(client, tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_device("other", "Other Device", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    db.create_session("sess1", "alice", "other", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess1")
    registered = client.post("/api/devices/register").json()

    response = client.get("/api/devices")

    assert response.status_code == 200
    ids = {d["id"] for d in response.json()}
    assert ids == {"other", registered["id"]}


def test_forget_device_deletes_an_unknown_returns_404(client, tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_session("sess1", "alice", "default", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess1")
    client.post("/api/devices/register")

    response = client.delete("/api/devices/nope")

    assert response.status_code == 404


def test_forget_device_removes_it(client, tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_session("sess1", "alice", "default", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess1")
    # A device other than the one issuing this request — forgetting your own
    # active device is refused (see the test below).
    db.create_device("other", "Other Device", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    client.post("/api/devices/register")

    response = client.delete("/api/devices/other")

    assert response.status_code == 200
    assert db.get_device("other") is None


def test_forget_device_deletes_that_devices_widget_layout_only(client, tmp_db):
    # Layout is keyed by (user, device, breakpoint) — forgetting a device
    # drops that screen's saved tile positions but must leave the same
    # user's layout on the device they're forgetting it from untouched.
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_session("sess1", "alice", "default", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess1")
    db.create_device("other", "Other Device", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
    db.save_widget_layout("alice", "other", "wide", "clock", {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1})
    this_device = client.post("/api/devices/register").json()["id"]
    db.save_widget_layout("alice", this_device, "wide", "clock", {"col": 3, "row": 1, "colSpan": 1, "rowSpan": 1})

    response = client.delete("/api/devices/other")

    assert response.status_code == 200
    assert db.get_widget_layout("alice", "other", "wide", "clock") is None
    assert db.get_widget_layout("alice", this_device, "wide", "clock") == {
        "col": 3,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }


def test_forget_device_refuses_to_delete_the_current_device(client, tmp_db):
    db.create_user("alice", "Alice", None, None, None, None, "2026-01-01T00:00:00Z")
    db.create_session("sess1", "alice", "default", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
    client.cookies.set("tilora_session", "sess1")
    device_id = client.post("/api/devices/register").json()["id"]

    response = client.delete(f"/api/devices/{device_id}")

    assert response.status_code == 400
    assert db.get_device(device_id) is not None
