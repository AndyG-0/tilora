from __future__ import annotations

import asyncio
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import hdhomerun
from app.auth import get_current_user
from app.plugins.base import registry
from app.plugins.hdhomerun.plugin import HDHomeRunPlugin


def register_plugin(**settings) -> HDHomeRunPlugin:
    merged = {**HDHomeRunPlugin.network_default_settings, **HDHomeRunPlugin.default_settings, **settings}
    plugin = HDHomeRunPlugin({"id": "hdhr1", "settings": merged})
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


def test_unknown_widget_returns_404(client):
    response = client.get("/api/hdhomerun/nope/stream/4.1")
    assert response.status_code == 404


def test_stream_channel_requires_login(unauthenticated_client):
    register_plugin(tuner_host="hdhr.local")
    response = unauthenticated_client.get("/api/hdhomerun/hdhr1/stream/4.1")
    assert response.status_code == 401


def test_playlist_requires_login(unauthenticated_client):
    register_plugin(tuner_host="hdhr.local")
    response = unauthenticated_client.get("/api/hdhomerun/hdhr1/playlist/4.1")
    assert response.status_code == 401


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
    assert "channel 4.1" in detail
    # The point of the 502 is the reason, not the fact — asserting only the
    # prefix is what let an empty stderr tail ship unnoticed.
    assert "HTTP error 503 Service Unavailable" in detail
    assert fake_process.terminate_calls == 1


class _SlowStreamReader(_FakeStreamReader):
    """A reader that doesn't produce its data on the first event-loop turn.

    Reproduces the race the drain-completion Event exists to close: the
    stderr drain runs as a detached task, so stdout EOF can reach the failure
    branch before stderr has been read at all.
    """

    def __init__(self, chunks: list[bytes], turns: int = 5):
        super().__init__(chunks)
        self._turns = turns

    async def read(self, n: int) -> bytes:
        for _ in range(self._turns):
            await asyncio.sleep(0)
        self._turns = 0
        return await super().read(n)


def test_stream_channel_502_waits_for_stderr_before_reporting(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")
    fake_process = _FakeProcess([])
    fake_process.stderr = _SlowStreamReader([b"[AVHWDeviceContext @ 0x0] No VA display found for device\n"])

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 502
    assert "No VA display found for device" in response.json()["detail"]


def test_stream_channel_502_distinguishes_an_exited_ffmpeg_from_a_silent_one(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")
    fake_process = _FakeProcess([], stderr_chunks=[b"boom\n"])
    fake_process.returncode = 218

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 502
    assert "exited with code 218" in response.json()["detail"]


def test_stream_channel_logs_the_command_and_ffmpeg_output_on_failure(client, monkeypatch, caplog):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")
    fake_process = _FakeProcess([], stderr_chunks=[b"Cannot load libva\n"])

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    with caplog.at_level(logging.ERROR, logger="app.api.hdhomerun"):
        client.get("/api/hdhomerun/hdhr1/stream/4.1")

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "Cannot load libva" in logged
    # The full command line, so a bug report doesn't need the settings too.
    assert "ffmpeg -hide_banner" in logged


def test_stream_channel_probes_hardware_after_a_hwaccel_preset_fails(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode", hwaccel="vaapi")
    fake_process = _FakeProcess([], stderr_chunks=[b"Device creation failed: -22.\n"])

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    async def fake_probe(settings, **kwargs):
        return {"ok": False, "command": "ffmpeg ...", "exit_code": 1, "output": "Device creation failed: -22."}

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(hdhomerun.hwaccel, "probe_transcode", fake_probe)

    response = client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert response.status_code == 502
    assert "hardware-acceleration problem" in response.json()["detail"]


def test_stream_channel_does_not_probe_hardware_for_a_software_preset(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")
    fake_process = _FakeProcess([], stderr_chunks=[b"Connection refused\n"])
    probed = False

    async def fake_create_subprocess_exec(*args, **kwargs):
        return fake_process

    async def fake_probe(settings, **kwargs):
        nonlocal probed
        probed = True
        return {"ok": True, "command": "ffmpeg ...", "exit_code": 0, "output": ""}

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(hdhomerun.hwaccel, "probe_transcode", fake_probe)

    client.get("/api/hdhomerun/hdhr1/stream/4.1")

    assert probed is False


def test_hwaccel_diagnostics_returns_the_report(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode", hwaccel="vaapi")
    report = {"device": "/dev/dri/renderD128", "summary": ["all good"], "probes": {}}

    async def fake_full_report(device=None, extra_settings=None):
        assert device == "/dev/dri/renderD128"
        assert extra_settings["hwaccel"] == "vaapi"
        return report

    monkeypatch.setattr(hdhomerun.hwaccel, "full_report", fake_full_report)

    response = client.get("/api/hdhomerun/hdhr1/hwaccel-diagnostics")

    assert response.status_code == 200
    assert response.json() == report


def test_hwaccel_diagnostics_honours_an_explicit_device(client, monkeypatch):
    register_plugin(tuner_host="hdhr.local", playback_mode="server_transcode", hwaccel="vaapi")

    async def fake_full_report(device=None, extra_settings=None):
        return {"device": device, "summary": [], "probes": {}}

    monkeypatch.setattr(hdhomerun.hwaccel, "full_report", fake_full_report)

    response = client.get("/api/hdhomerun/hdhr1/hwaccel-diagnostics?device=/dev/dri/renderD129")

    assert response.json()["device"] == "/dev/dri/renderD129"


def test_hwaccel_diagnostics_is_admin_only(member_client):
    register_plugin(tuner_host="hdhr.local")
    response = member_client.get("/api/hdhomerun/hdhr1/hwaccel-diagnostics")
    assert response.status_code == 403


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


def test_recording_stream_threads_start_and_audio_index_into_ffmpeg_args(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000, playback_mode="server_transcode")
    fake_process = _FakeProcess([b"abc"])
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/recording-stream?url=/recorded/play?id=123&start=90.5&audio_index=1")

    assert response.status_code == 200
    args = captured["args"]
    assert args[args.index("-ss") + 1] == "90.500"
    assert args.index("-ss") < args.index("-i")
    assert args[args.index("-map") + 1] == "0:v:0"
    assert "0:a:1" in args


def test_recording_stream_omits_seek_and_audio_map_when_not_given(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000, playback_mode="server_transcode")
    fake_process = _FakeProcess([b"abc"])
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return fake_process

    monkeypatch.setattr(hdhomerun.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    response = client.get("/api/hdhomerun/hdhr1/recording-stream?url=/recorded/play?id=123")

    assert response.status_code == 200
    args = captured["args"]
    assert "-ss" not in args
    assert "-map" not in args


def test_recording_detail_in_progress_when_record_end_missing(client):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)

    response = client.get(
        "/api/hdhomerun/hdhr1/recording-detail?url=/recorded/play?id=1&recording_id=rec1&start=1700000000"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_in_progress"] is True
    assert body["video"] is None
    assert body["audio"] == []
    assert body["has_captions"] is False
    assert body["duration_seconds"] is not None


def test_recording_detail_in_progress_when_record_end_in_future(client):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)
    future = time.time() + 3600

    response = client.get(
        f"/api/hdhomerun/hdhr1/recording-detail?url=/recorded/play?id=1&recording_id=rec2"
        f"&start={time.time()}&record_end={future}"
    )

    assert response.status_code == 200
    assert response.json()["is_in_progress"] is True


def test_recording_detail_completed_probes_and_caches(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)
    probe_calls = 0

    async def fake_probe(url):
        nonlocal probe_calls
        probe_calls += 1
        return {
            "duration_seconds": 1800.0,
            "video": {"codec": "h264", "width": 1920, "height": 1080, "fps": 29.97},
            "audio": [{"index": 0, "codec": "aac", "channels": 2, "language": "eng"}],
            "has_captions": True,
        }

    monkeypatch.setattr(hdhomerun.media_probe, "probe", fake_probe)
    hdhomerun._probe_cache.pop("rec3", None)

    past = time.time() - 60
    url = f"/api/hdhomerun/hdhr1/recording-detail?url=/recorded/play?id=1&recording_id=rec3&start=0&record_end={past}"
    response = client.get(url)
    assert response.status_code == 200
    body = response.json()
    assert body["is_in_progress"] is False
    assert body["duration_seconds"] == 1800.0
    assert body["has_captions"] is True

    # Second request for the same recording reuses the cached probe result.
    client.get(url)
    assert probe_calls == 1
    hdhomerun._probe_cache.pop("rec3", None)


def test_recording_detail_falls_back_when_probe_fails(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)

    async def fake_probe(url):
        return None

    monkeypatch.setattr(hdhomerun.media_probe, "probe", fake_probe)
    hdhomerun._probe_cache.pop("rec4", None)

    past = time.time() - 60
    response = client.get(
        f"/api/hdhomerun/hdhr1/recording-detail?url=/recorded/play?id=1&recording_id=rec4&start=0&record_end={past}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_in_progress"] is False
    assert body["duration_seconds"] == past
    assert body["video"] is None
    hdhomerun._probe_cache.pop("rec4", None)


def test_recording_captions_404_for_in_progress_recording(client):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)

    response = client.get("/api/hdhomerun/hdhr1/recording-captions.vtt?url=/recorded/play?id=1&recording_id=rec5")

    assert response.status_code == 404


def test_recording_captions_returns_file_when_generated(client, monkeypatch, tmp_path):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)
    vtt_path = tmp_path / "rec6.vtt"
    vtt_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n")

    async def fake_generate(url, recording_id):
        return vtt_path

    monkeypatch.setattr(hdhomerun.media_cache, "generate_captions_vtt", fake_generate)

    past = time.time() - 60
    response = client.get(
        f"/api/hdhomerun/hdhr1/recording-captions.vtt?url=/recorded/play?id=1&recording_id=rec6&record_end={past}"
    )

    assert response.status_code == 200
    assert "WEBVTT" in response.text


def test_recording_captions_404_when_generation_fails(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)

    async def fake_generate(url, recording_id):
        return None

    monkeypatch.setattr(hdhomerun.media_cache, "generate_captions_vtt", fake_generate)

    past = time.time() - 60
    response = client.get(
        f"/api/hdhomerun/hdhr1/recording-captions.vtt?url=/recorded/play?id=1&recording_id=rec7&record_end={past}"
    )

    assert response.status_code == 404


def test_recording_thumbnails_404_when_disabled_in_settings(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000, thumbnails_enabled=False)

    async def fake_generate(url, recording_id, duration_seconds):
        raise AssertionError("should not generate thumbnails when disabled")

    monkeypatch.setattr(hdhomerun.media_cache, "generate_thumbnail_sprite", fake_generate)

    past = time.time() - 60
    response = client.get(
        f"/api/hdhomerun/hdhr1/recording-thumbnails/rec8.jpg?url=/recorded/play?id=1&record_end={past}"
    )

    assert response.status_code == 404


def test_recording_thumbnails_404_for_in_progress_recording(client):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)

    response = client.get("/api/hdhomerun/hdhr1/recording-thumbnails/rec9.jpg?url=/recorded/play?id=1")

    assert response.status_code == 404


def test_recording_thumbnails_returns_sprite_and_vtt_when_generated(client, monkeypatch, tmp_path):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)
    jpg_path = tmp_path / "rec10.jpg"
    jpg_path.write_bytes(b"\xff\xd8\xff")
    vtt_path = tmp_path / "rec10.thumbs.vtt"
    vtt_path.write_text("WEBVTT\n")

    async def fake_probe(url):
        return {"duration_seconds": 600.0, "video": None, "audio": [], "has_captions": False}

    async def fake_generate(url, recording_id, duration_seconds):
        assert duration_seconds == 600.0
        return jpg_path, vtt_path

    monkeypatch.setattr(hdhomerun.media_probe, "probe", fake_probe)
    monkeypatch.setattr(hdhomerun.media_cache, "generate_thumbnail_sprite", fake_generate)
    hdhomerun._probe_cache.pop("rec10", None)

    past = time.time() - 60
    jpg_response = client.get(
        f"/api/hdhomerun/hdhr1/recording-thumbnails/rec10.jpg?url=/recorded/play?id=1&record_end={past}"
    )
    vtt_response = client.get(
        f"/api/hdhomerun/hdhr1/recording-thumbnails/rec10.vtt?url=/recorded/play?id=1&record_end={past}"
    )

    assert jpg_response.status_code == 200
    assert jpg_response.headers["content-type"] == "image/jpeg"
    assert vtt_response.status_code == 200
    assert "WEBVTT" in vtt_response.text
    hdhomerun._probe_cache.pop("rec10", None)


def test_recording_thumbnails_404_when_duration_unknown(client, monkeypatch):
    register_plugin(dvr_host="dvr.local", dvr_port=50000)

    async def fake_probe(url):
        return None

    monkeypatch.setattr(hdhomerun.media_probe, "probe", fake_probe)
    hdhomerun._probe_cache.pop("rec11", None)

    past = time.time() - 60
    response = client.get(
        f"/api/hdhomerun/hdhr1/recording-thumbnails/rec11.jpg?url=/recorded/play?id=1&record_end={past}"
    )

    assert response.status_code == 404
    hdhomerun._probe_cache.pop("rec11", None)
