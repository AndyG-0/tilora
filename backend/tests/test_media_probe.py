from __future__ import annotations

import json

from app import media_probe


class _FakeProcess:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, input: bytes | None = None):
        return self._stdout, self._stderr

    def kill(self) -> None:
        pass


def _payload(*, closed_captions: int | None = 0) -> dict:
    video_stream = {
        "index": 0,
        "codec_type": "video",
        "codec_name": "mpeg2video",
        "width": 1280,
        "height": 720,
        "avg_frame_rate": "60000/1001",
    }
    if closed_captions is not None:
        video_stream["closed_captions"] = closed_captions
    return {
        "format": {"duration": "1771.49"},
        "streams": [
            video_stream,
            {"index": 1, "codec_type": "audio", "codec_name": "ac3", "channels": 6, "tags": {"language": "eng"}},
        ],
    }


async def test_probe_requests_analyze_frames_so_closed_captions_gets_populated(monkeypatch):
    # closed_captions is only emitted by ffprobe when frame decoding is
    # requested (-analyze_frames) — without it, the field is silently absent
    # from every stream regardless of whether captions are actually present.
    # See media_probe.py's module docstring/comment for the ffprobe.c source
    # reference that drives this.
    captured_argv: list[str] = []

    async def fake_exec(*argv, **kwargs):
        captured_argv.extend(argv)
        return _FakeProcess(stdout=json.dumps(_payload(closed_captions=1)).encode())

    monkeypatch.setattr(media_probe.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_probe.probe("http://dvr.local/recorded/play?id=1")

    assert "-analyze_frames" in captured_argv
    assert captured_argv.index("-read_intervals") + 1 < len(captured_argv)
    assert result is not None
    assert result["has_captions"] is True


async def test_probe_reports_no_captions_when_ffprobe_omits_the_field(monkeypatch):
    async def fake_exec(*argv, **kwargs):
        return _FakeProcess(stdout=json.dumps(_payload(closed_captions=None)).encode())

    monkeypatch.setattr(media_probe.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_probe.probe("url")

    assert result is not None
    assert result["has_captions"] is False


async def test_probe_extracts_duration_video_and_audio(monkeypatch):
    async def fake_exec(*argv, **kwargs):
        return _FakeProcess(stdout=json.dumps(_payload(closed_captions=0)).encode())

    monkeypatch.setattr(media_probe.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_probe.probe("url")

    assert result is not None
    assert result["duration_seconds"] == 1771.49
    assert result["video"] == {"codec": "mpeg2video", "width": 1280, "height": 720, "fps": 59.94}
    assert result["audio"] == [{"index": 0, "codec": "ac3", "channels": 6, "language": "eng"}]


async def test_probe_returns_none_on_nonzero_exit(monkeypatch):
    async def fake_exec(*argv, **kwargs):
        return _FakeProcess(stdout=b"", returncode=1)

    monkeypatch.setattr(media_probe.asyncio, "create_subprocess_exec", fake_exec)

    assert await media_probe.probe("url") is None


async def test_probe_returns_none_on_missing_binary(monkeypatch):
    async def fake_exec(*argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "ffprobe")

    monkeypatch.setattr(media_probe.asyncio, "create_subprocess_exec", fake_exec)

    assert await media_probe.probe("url") is None
