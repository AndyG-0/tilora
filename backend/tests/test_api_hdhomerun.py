from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import hdhomerun
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.hdhomerun.plugin import HDHomeRunPlugin


def register_plugin(**settings) -> HDHomeRunPlugin:
    plugin = HDHomeRunPlugin({"id": "hdhr1", "settings": {**HDHomeRunPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(hdhomerun.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(hdhomerun.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member", "role": "member"}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    app = FastAPI()
    app.include_router(hdhomerun.router)
    return TestClient(app)


def test_unknown_widget_returns_404_for_tuner_test(client):
    response = client.post("/api/hdhomerun/nope/test-tuner-connection", json={})
    assert response.status_code == 404


def test_unknown_widget_returns_404_for_dvr_test(client):
    response = client.post("/api/hdhomerun/nope/test-dvr-connection", json={})
    assert response.status_code == 404


def test_test_tuner_connection_requires_login(unauthenticated_client):
    register_plugin(tuner_host="hdhr.local")
    response = unauthenticated_client.post("/api/hdhomerun/hdhr1/test-tuner-connection", json={})
    assert response.status_code == 401


def test_test_tuner_connection_rejects_member(member_client):
    register_plugin(tuner_host="hdhr.local")
    response = member_client.post("/api/hdhomerun/hdhr1/test-tuner-connection", json={})
    assert response.status_code == 403


def test_test_dvr_connection_requires_login(unauthenticated_client):
    register_plugin(dvr_host="dvr.local")
    response = unauthenticated_client.post("/api/hdhomerun/hdhr1/test-dvr-connection", json={})
    assert response.status_code == 401


def test_test_dvr_connection_rejects_member(member_client):
    register_plugin(dvr_host="dvr.local")
    response = member_client.post("/api/hdhomerun/hdhr1/test-dvr-connection", json={})
    assert response.status_code == 403


def test_stream_channel_requires_login(unauthenticated_client):
    register_plugin(tuner_host="hdhr.local")
    response = unauthenticated_client.get("/api/hdhomerun/hdhr1/stream/4.1")
    assert response.status_code == 401


def test_playlist_requires_login(unauthenticated_client):
    register_plugin(tuner_host="hdhr.local")
    response = unauthenticated_client.get("/api/hdhomerun/hdhr1/playlist/4.1")
    assert response.status_code == 401


@respx.mock
def test_test_tuner_connection_ok(client):
    register_plugin(tuner_host="hdhr.local")
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun FLEX"})
    )

    response = client.post("/api/hdhomerun/hdhr1/test-tuner-connection", json={})

    assert response.json() == {"ok": True, "name": "HDHomeRun FLEX", "error": None}


@respx.mock
def test_test_tuner_connection_uses_candidate_settings_override(client):
    register_plugin(tuner_host="hdhr.local")
    route = respx.get("http://other.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "Other Tuner"})
    )

    response = client.post("/api/hdhomerun/hdhr1/test-tuner-connection", json={"tuner_host": "other.local"})

    assert route.called
    assert response.json()["name"] == "Other Tuner"


@respx.mock
def test_test_tuner_connection_reports_failure_without_raising(client):
    register_plugin(tuner_host="hdhr.local")
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(500))

    response = client.post("/api/hdhomerun/hdhr1/test-tuner-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]


@respx.mock
def test_test_dvr_connection_ok(client):
    register_plugin(dvr_host="dvr.local")
    respx.get("http://dvr.local:59090/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun RECORD"})
    )

    response = client.post("/api/hdhomerun/hdhr1/test-dvr-connection", json={})

    assert response.json() == {"ok": True, "name": "HDHomeRun RECORD", "error": None}


@respx.mock
def test_test_dvr_connection_reports_failure_without_raising(client):
    register_plugin(dvr_host="dvr.local")
    respx.get("http://dvr.local:59090/discover.json").mock(return_value=httpx.Response(500))

    response = client.post("/api/hdhomerun/hdhr1/test-dvr-connection", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]


def test_transcode_presets_lists_software_and_custom(client):
    response = client.get("/api/hdhomerun/transcode-presets")

    assert response.status_code == 200
    ids = {p["id"] for p in response.json()}
    assert "software" in ids
    assert "custom" in ids
    software = next(p for p in response.json() if p["id"] == "software")
    assert software["label"]
    assert software["description"]
    assert "-c:v" in software["output_args"]


def test_stream_channel_returns_404_when_tuner_not_configured(client):
    register_plugin()

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 404


class _FakeStreamReader:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    async def read(self, n: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _FakeProcess:
    def __init__(self, chunks: list[bytes], stderr_chunks: list[bytes] | None = None):
        self.stdout = _FakeStreamReader(chunks)
        self.stderr = _FakeStreamReader(stderr_chunks or [])
        self.returncode: int | None = None
        self.terminate_calls = 0

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = 0

    async def wait(self) -> int | None:
        return self.returncode


def test_stream_channel_transcodes_streams_chunks_and_terminates_ffmpeg(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")
    fake_process = _FakeProcess([b"abc", b"def"])
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 200
    assert response.content == b"abcdef"
    assert fake_process.terminate_calls == 1
    args = captured["args"]
    assert args[0] == "ffmpeg"
    assert "http://hdhr.local:5004/auto/v4.1" in args
    assert "libx264" in args


def test_stream_channel_uses_configured_hwaccel_preset(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode", hwaccel="vaapi")
    fake_process = _FakeProcess([b"abc"])
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 200
    args = captured["args"]
    assert "h264_vaapi" in args
    assert "libx264" not in args


def test_stream_channel_uses_custom_ffmpeg_args(client, monkeypatch):
    register_plugin(
        tuner_host="hdhr.local",
        playback_mode="server_transcode",
        hwaccel="custom",
        custom_ffmpeg_args="-c:v h264_v4l2m2m -b:v 4M -c:a aac",
    )
    fake_process = _FakeProcess([b"abc"])
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 200
    args = captured["args"]
    assert "h264_v4l2m2m" in args
    assert "4M" in args


def test_stream_channel_returns_400_for_unparseable_custom_ffmpeg_args(client, monkeypatch):
    register_plugin(
        tuner_host="hdhr.local",
        playback_mode="server_transcode",
        hwaccel="custom",
        custom_ffmpeg_args='-c:v "libx264',
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        raise AssertionError("ffmpeg should never be spawned for unparseable args")

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 400
    assert "invalid custom ffmpeg arguments" in response.json()["detail"].lower()


def test_stream_channel_returns_502_when_ffmpeg_produces_no_output(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")
    fake_process = _FakeProcess([], stderr_chunks=[b"[http @ 0x0] HTTP error 503 Service Unavailable\n"])

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "ffmpeg failed to start streaming channel 4.1" in detail
    assert fake_process.terminate_calls == 1


def test_stream_channel_returns_503_when_ffmpeg_missing(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")

    async def fake_create_subprocess_exec(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 503
    assert "ffmpeg" in response.json()["detail"]


def test_playlist_returns_404_when_tuner_not_configured(client):
    register_plugin()

    response = client.get("/api/hdhomerun/hdhr1/playlist/4.1")

    assert response.status_code == 404


def test_playlist_returns_m3u_pointing_at_raw_stream(client):
    register_plugin(tuner_host="hdhr.local")

    response = client.get("/api/hdhomerun/hdhr1/playlist/4.1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/x-mpegurl")
    assert response.headers["content-disposition"] == 'inline; filename="4.1.m3u"'
    assert response.text.startswith("#EXTM3U\n")
    assert "http://hdhr.local:5004/auto/v4.1" in response.text
