from __future__ import annotations

from app.plugins.hdhomerun import media_cache


class _FakeProcess:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.killed = False

    async def communicate(self, input: bytes | None = None):
        return b"", b""

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> None:
        pass


def test_escape_movie_filter_url_escapes_colons_in_addition_to_quotes_and_backslashes():
    # The movie filter's own option parser splits on the first unescaped ':'
    # after the filename to find ":options" - even inside single quotes - so
    # an http:// URL's scheme/port colons must be escaped or everything past
    # them (including query params) gets silently mis-parsed as filter
    # options and ffmpeg opens no video at all.
    escaped = media_cache._escape_movie_filter_url("http://192.168.50.197:50000/recorded/play?id=abc")
    assert escaped == "http\\://192.168.50.197\\:50000/recorded/play?id=abc"


def test_escape_movie_filter_url_escapes_backslash_and_quote():
    escaped = media_cache._escape_movie_filter_url(r"C:\weird'file.mpg")
    assert escaped == r"C\:\\weird\'file.mpg"


async def test_generate_captions_vtt_builds_argv_with_escaped_colons(monkeypatch, tmp_path):
    monkeypatch.setattr(media_cache, "HDHOMERUN_MEDIA_CACHE_DIR", tmp_path)

    captured_argv: list[str] = []

    async def fake_exec(*argv, **kwargs):
        captured_argv.extend(argv)
        # Simulate a successful ffmpeg run that wrote the output file.
        out_path = argv[-1]
        with open(out_path, "w") as f:
            f.write("WEBVTT\n")
        return _FakeProcess(returncode=0)

    monkeypatch.setattr(media_cache.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_cache.generate_captions_vtt("http://192.168.50.197:50000/recorded/play?id=abc", "rec1")

    assert result is not None
    assert result.read_text() == "WEBVTT\n"
    movie_arg = next(a for a in captured_argv if a.startswith("movie="))
    assert "192.168.50.197\\:50000" in movie_arg
    assert "http\\://" in movie_arg


async def test_generate_captions_vtt_does_not_permanently_cache_a_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(media_cache, "HDHOMERUN_MEDIA_CACHE_DIR", tmp_path)
    monkeypatch.setattr(media_cache, "_GENERATE_TIMEOUT_SECONDS", 0.01)

    class _HangingProcess(_FakeProcess):
        async def communicate(self, input: bytes | None = None):
            import asyncio

            await asyncio.sleep(10)
            return b"", b""

    async def fake_exec(*argv, **kwargs):
        return _HangingProcess()

    monkeypatch.setattr(media_cache.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_cache.generate_captions_vtt("url", "rec1")

    assert result is None
    cache_path = tmp_path / "rec1.vtt"
    assert not cache_path.exists()


async def test_generate_captions_vtt_caches_a_genuine_no_captions_result(monkeypatch, tmp_path):
    monkeypatch.setattr(media_cache, "HDHOMERUN_MEDIA_CACHE_DIR", tmp_path)

    async def fake_exec(*argv, **kwargs):
        # ffmpeg exits 0 but writes nothing - a genuine "no captions" run.
        return _FakeProcess(returncode=0)

    monkeypatch.setattr(media_cache.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_cache.generate_captions_vtt("url", "rec1")

    assert result is None
    cache_path = tmp_path / "rec1.vtt"
    assert cache_path.exists()
    assert cache_path.stat().st_size == 0


async def test_generate_captions_vtt_uses_cached_file_on_second_call(monkeypatch, tmp_path):
    monkeypatch.setattr(media_cache, "HDHOMERUN_MEDIA_CACHE_DIR", tmp_path)
    cache_path = tmp_path / "rec1.vtt"
    cache_path.write_text("WEBVTT\n")

    async def fake_exec(*argv, **kwargs):
        raise AssertionError("should not re-run ffmpeg when a cached result exists")

    monkeypatch.setattr(media_cache.asyncio, "create_subprocess_exec", fake_exec)

    result = await media_cache.generate_captions_vtt("url", "rec1")

    assert result == cache_path
