from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import jellyfin
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.jellyfin.plugin import JellyfinPlugin


def register_plugin(**settings) -> JellyfinPlugin:
    plugin = JellyfinPlugin({"id": "jf1", "settings": {**JellyfinPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jellyfin.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(jellyfin.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(jellyfin.router)
    return TestClient(app)


def test_unknown_widget_returns_404(client):
    response = client.get("/api/jellyfin/nope/libraries")
    assert response.status_code == 404


def test_test_connection_requires_login(unauthenticated_client):
    register_plugin(host="jf.local")
    response = unauthenticated_client.post("/api/jellyfin/jf1/test-connection", json={})
    assert response.status_code == 401


def test_test_connection_rejects_member(member_client):
    register_plugin(host="jf.local")
    response = member_client.post("/api/jellyfin/jf1/test-connection", json={})
    assert response.status_code == 403


def test_list_libraries_requires_login(unauthenticated_client):
    register_plugin(host="jf.local")
    response = unauthenticated_client.get("/api/jellyfin/jf1/libraries")
    assert response.status_code == 401


@respx.mock
def test_list_libraries_allows_member(member_client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Library/MediaFolders").mock(return_value=httpx.Response(200, json={"Items": []}))

    response = member_client.get("/api/jellyfin/jf1/libraries")

    assert response.status_code == 200


@respx.mock
def test_test_connection_ok(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/System/Info").mock(
        return_value=httpx.Response(200, json={"ServerName": "Home Server"})
    )

    response = client.post("/api/jellyfin/jf1/test-connection", json={})

    assert response.json() == {"ok": True, "server_name": "Home Server", "error": None}


@respx.mock
def test_test_connection_uses_candidate_settings_override(client):
    register_plugin(host="jf.local", api_key="k1")
    route = respx.get("http://other.local:8096/System/Info").mock(
        return_value=httpx.Response(200, json={"ServerName": "Other Server"})
    )

    response = client.post("/api/jellyfin/jf1/test-connection", json={"host": "other.local"})

    assert route.called
    assert response.json()["server_name"] == "Other Server"


@respx.mock
def test_test_connection_reports_failure_without_raising(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/System/Info").mock(return_value=httpx.Response(500))

    response = client.post("/api/jellyfin/jf1/test-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]


@respx.mock
def test_list_libraries(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Library/MediaFolders").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "lib1", "Name": "Movies", "IsFolder": True}]})
    )

    response = client.get("/api/jellyfin/jf1/libraries")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "lib1"


@respx.mock
def test_get_image_proxies_bytes(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Items/pic1/Images/Primary").mock(
        return_value=httpx.Response(200, content=b"imgbytes", headers={"content-type": "image/jpeg"})
    )

    response = client.get("/api/jellyfin/jf1/images/pic1")

    assert response.status_code == 200
    assert response.content == b"imgbytes"
    assert response.headers["content-type"] == "image/jpeg"


def test_get_image_404_when_not_configured(client):
    register_plugin()

    response = client.get("/api/jellyfin/jf1/images/pic1")

    assert response.status_code == 404


@respx.mock
def test_stream_forwards_range_header_and_status(client):
    register_plugin(host="jf.local", api_key="k1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("range") == "bytes=100-"
        return httpx.Response(
            206,
            content=b"partial-bytes",
            headers={"content-range": "bytes 100-199/200", "accept-ranges": "bytes", "content-type": "video/mp4"},
        )

    respx.get("http://jf.local:8096/Videos/vid1/stream").mock(side_effect=handler)

    response = client.get("/api/jellyfin/jf1/stream/vid1", headers={"Range": "bytes=100-"})

    assert response.status_code == 206
    assert response.content == b"partial-bytes"
    assert response.headers["content-range"] == "bytes 100-199/200"
    assert response.headers["accept-ranges"] == "bytes"
