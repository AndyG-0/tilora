from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import devices as devices_api
from app.api import users as users_api
from app.auth import SESSION_COOKIE_NAME
from app.storage import db


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(devices_api.router)
    app.include_router(users_api.router)
    return TestClient(app)


def test_list_profiles_is_empty_on_a_fresh_install(client, tmp_db):
    response = client.get("/api/users")

    assert response.status_code == 200
    assert response.json() == []


def test_create_profile_requires_a_device_cookie(client, tmp_db):
    response = client.post("/api/users", json={"name": "Alice"})

    assert response.status_code == 401


def test_create_profile_logs_the_new_user_in(client, tmp_db):
    client.post("/api/devices/register")

    response = client.post("/api/users", json={"name": "Alice", "avatar": "cat.png"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alice"
    assert body["avatar"] == "cat.png"
    assert SESSION_COOKIE_NAME in response.cookies

    me = client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Alice"


def test_create_profile_rejects_a_malformed_pin(client, tmp_db):
    client.post("/api/devices/register")

    response = client.post("/api/users", json={"name": "Alice", "pin": "abc"})

    assert response.status_code == 422


def test_login_with_no_pin_set_succeeds_without_a_pin(client, tmp_db):
    client.post("/api/devices/register")
    profile = client.post("/api/users", json={"name": "Alice"}).json()
    client.post("/api/users/logout")

    response = client.post(f"/api/users/{profile['id']}/login", json={})

    assert response.status_code == 200
    assert SESSION_COOKIE_NAME in response.cookies


def test_login_for_an_unknown_profile_returns_404(client, tmp_db):
    client.post("/api/devices/register")

    response = client.post("/api/users/nope/login", json={})

    assert response.status_code == 404


def test_login_with_a_pin_requires_the_correct_pin(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/users", json={"name": "Bob", "pin": "1234"})
    client.post("/api/users/logout")

    wrong = client.post(f"/api/users/{db.list_users()[-1]['id']}/login", json={"pin": "0000"})
    assert wrong.status_code == 401

    correct = client.post(f"/api/users/{db.list_users()[-1]['id']}/login", json={"pin": "1234"})
    assert correct.status_code == 200


def test_logout_clears_the_session(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/users", json={"name": "Alice"})

    response = client.post("/api/users/logout")

    assert response.status_code == 200
    assert client.get("/api/users/me").status_code == 401


def test_logout_without_a_session_still_succeeds(client, tmp_db):
    response = client.post("/api/users/logout")

    assert response.status_code == 200


def test_me_requires_a_session(client, tmp_db):
    response = client.get("/api/users/me")

    assert response.status_code == 401


def test_patch_me_updates_name_and_avatar(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/users", json={"name": "Alice"})

    response = client.patch("/api/users/me", json={"name": "Renamed", "avatar": "dog.png"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["avatar"] == "dog.png"


def test_patch_me_can_set_and_then_clear_a_pin(client, tmp_db):
    client.post("/api/devices/register")
    profile = client.post("/api/users", json={"name": "Alice"}).json()

    client.patch("/api/users/me", json={"pin": "4321"})
    assert db.get_user(profile["id"])["pin_hash"] is not None

    client.patch("/api/users/me", json={"pin": ""})
    assert db.get_user(profile["id"])["pin_hash"] is None


def test_delete_me_refuses_to_delete_the_only_remaining_profile(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/users", json={"name": "Alice"})

    response = client.delete("/api/users/me")

    assert response.status_code == 400


def test_delete_me_succeeds_when_another_profile_exists(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/users", json={"name": "Alice"})
    bob = client.post("/api/users", json={"name": "Bob"}).json()

    response = client.delete("/api/users/me")

    assert response.status_code == 200
    assert db.get_user(bob["id"]) is None


def test_get_and_patch_preferences_round_trip(client, tmp_db):
    client.post("/api/devices/register")
    client.post("/api/users", json={"name": "Alice"})

    assert client.get("/api/users/me/preferences").json() == {"theme": "dark"}

    response = client.patch("/api/users/me/preferences", json={"theme": "light"})

    assert response.status_code == 200
    assert response.json() == {"theme": "light"}
    assert client.get("/api/users/me/preferences").json() == {"theme": "light"}
