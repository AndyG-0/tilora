from __future__ import annotations

import json

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
    merged = {**JellyfinPlugin.network_default_settings, **JellyfinPlugin.default_settings, **settings}
    plugin = JellyfinPlugin({"id": "jf1", "settings": merged})
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


@respx.mock
def test_get_item_detail_endpoint(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Items/m1").mock(
        return_value=httpx.Response(200, json={"Id": "m1", "Name": "Movie Title", "Type": "Movie"})
    )

    response = client.get("/api/jellyfin/jf1/detail/m1")

    assert response.status_code == 200
    assert response.json()["name"] == "Movie Title"


@respx.mock
def test_get_subtitle_endpoint(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Videos/m1/Subtitles/2/0/Stream.vtt").mock(
        return_value=httpx.Response(200, content=b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCaption text")
    )

    response = client.get("/api/jellyfin/jf1/subtitles/m1/2.vtt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vtt")
    assert b"WEBVTT" in response.content


@respx.mock
def test_hls_master_playlist_rewrites_uris(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Videos/vid1/master.m3u8").mock(
        return_value=httpx.Response(200, text="#EXTM3U\nmain/0.m3u8\n")
    )

    response = client.get("/api/jellyfin/jf1/hls/vid1/master.m3u8?play_session_id=sess1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.apple.mpegurl"
    assert "/api/jellyfin/jf1/hls-resource/vid1?path=" in response.text
    assert "main%2F0.m3u8" in response.text


@respx.mock
def test_hls_master_playlist_forwards_audio_stream_index(client):
    register_plugin(host="jf.local", api_key="k1")

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(httpx.QueryParams(request.url.query))
        assert params.get("AudioStreamIndex") == "3"
        return httpx.Response(200, text="#EXTM3U\n")

    respx.get("http://jf.local:8096/Videos/vid1/master.m3u8").mock(side_effect=handler)

    response = client.get("/api/jellyfin/jf1/hls/vid1/master.m3u8?play_session_id=sess1&audio_stream_index=3")

    assert response.status_code == 200


@respx.mock
def test_hls_resource_streams_segment_bytes(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Videos/vid1/0.ts", params={"a": "1"}).mock(
        return_value=httpx.Response(200, content=b"segment-bytes", headers={"content-type": "video/mp2t"})
    )

    response = client.get("/api/jellyfin/jf1/hls-resource/vid1", params={"path": "/Videos/vid1/0.ts?a=1"})

    assert response.status_code == 200
    assert response.content == b"segment-bytes"


@respx.mock
def test_hls_resource_rewrites_nested_variant_playlist(client):
    register_plugin(host="jf.local", api_key="k1")
    respx.get("http://jf.local:8096/Videos/vid1/main/master.m3u8").mock(
        return_value=httpx.Response(
            200, text="#EXTM3U\n0.ts\n", headers={"content-type": "application/vnd.apple.mpegurl"}
        )
    )

    response = client.get("/api/jellyfin/jf1/hls-resource/vid1", params={"path": "/Videos/vid1/main/master.m3u8"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.apple.mpegurl"
    assert "main%2F0.ts" in response.text


@respx.mock
def test_playback_stopped_calls_jellyfin_and_returns_ok(client):
    register_plugin(host="jf.local", api_key="k1")
    route = respx.post("http://jf.local:8096/Sessions/Playing/Stopped").mock(return_value=httpx.Response(204))

    response = client.post("/api/jellyfin/jf1/playback-stopped/vid1?play_session_id=sess1&position_seconds=12.5")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert route.called
    assert json.loads(route.calls.last.request.content)["PositionTicks"] == 125_000_000


@respx.mock
def test_playback_started_calls_jellyfin_and_returns_ok(client):
    register_plugin(host="jf.local", api_key="k1")
    route = respx.post("http://jf.local:8096/Sessions/Playing").mock(return_value=httpx.Response(204))

    response = client.post("/api/jellyfin/jf1/playback-started/vid1?play_session_id=sess1")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert route.called
    assert json.loads(route.calls.last.request.content)["ItemId"] == "vid1"


@respx.mock
def test_playback_progress_calls_jellyfin_and_returns_ok(client):
    register_plugin(host="jf.local", api_key="k1")
    route = respx.post("http://jf.local:8096/Sessions/Playing/Progress").mock(return_value=httpx.Response(204))

    response = client.post(
        "/api/jellyfin/jf1/playback-progress/vid1?play_session_id=sess1&position_seconds=45&is_paused=true"
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["PositionTicks"] == 450_000_000
    assert body["IsPaused"] is True
