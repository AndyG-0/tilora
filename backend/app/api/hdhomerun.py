"""HDHomeRun stream-proxy routes.

Most of what the widget needs (lineup, guide, tuner status, DVR recordings)
already fits the generic summary/detail JSON shape handled by
`app/api/widgets.py`. This router covers what doesn't: transcoding a
channel's raw MPEG-2 stream to H.264/AAC via a local `ffmpeg` subprocess when
`playback_mode` is "server_transcode" so it's playable in-browser; and
handing a channel's raw stream off to a native player app for "Open in
external player" — no browser can decode raw MPEG-2 itself, and a bare link
to the MPEG-TS URL just downloads an opaque blob, so `/playlist` wraps it in
a tiny `.m3u` file instead, which the OS/browser hands to whatever's
registered for playlists (VLC, IINA, etc). Connection settings (tuner/DVR
host, port) are edited at the network level now (see
`app/api/network_settings.py`), not per-widget.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shlex
import time
from collections import OrderedDict
from collections.abc import Coroutine
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app import hwaccel, media_probe, transcoding
from app.auth import get_current_admin, get_current_user
from app.integrations import hdhomerun_client
from app.plugins.base import get_typed_plugin
from app.plugins.hdhomerun import media_cache
from app.plugins.hdhomerun.plugin import HDHomeRunPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hdhomerun", tags=["hdhomerun"], dependencies=[Depends(get_current_user)])

_STREAM_CHUNK_BYTES = 64 * 1024
_FFMPEG_STARTUP_TIMEOUT_SECONDS = 8
_FFMPEG_TERMINATE_TIMEOUT_SECONDS = 5
_DISCONNECT_POLL_INTERVAL_SECONDS = 1
_STDERR_TAIL_BYTES = 4000
# How long to wait for the stderr drain to reach EOF once ffmpeg has failed,
# before giving up and reporting whatever was captured.
_STDERR_FLUSH_TIMEOUT_SECONDS = 2
# Ceiling on the diagnostic test-transcode run after a hwaccel preset fails.
# It's spent on a request that has already failed, so it has to stay small
# enough not to turn a quick error into an apparent hang.
_FAILURE_PROBE_TIMEOUT_SECONDS = 15
# Only the tail end of ffmpeg's output goes in the HTTP response; the log line
# gets all of it.
_DETAIL_REASON_CHARS = 500

# Cleanup/drain tasks (killing ffmpeg, draining its stderr) are fired from
# here instead of being awaited directly, and tracked in this set purely so
# asyncio doesn't garbage-collect a task mid-flight — see `_run_in_background`.
_background_tasks: set[asyncio.Task[None]] = set()

# Nothing else limits how many ffmpeg transcodes can run at once, and each is
# a real CPU/GPU cost — enough concurrent stream/recording requests can OOM
# or thrash a Pi. Held for the life of the stream, not just around the spawn
# (see `_terminate_and_release`), so this caps concurrent transcodes rather
# than just concurrent spawns.
_ffmpeg_semaphore = asyncio.Semaphore(2)

# ffprobe metadata for a completed recording never changes, so it's cached
# in-process per recording_id rather than re-run on every /recording-detail
# poll (the player refetches this periodically while a recording is still
# in-progress, but once it flips to completed the same result is reused).
# Capped and LRU-evicted (via move_to_end/popitem) so a DVR that's been
# recording for months doesn't grow this without bound.
_PROBE_CACHE_MAX_ENTRIES = 500
_probe_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()


def _probe_cache_set(recording_id: str, result: dict[str, Any]) -> None:
    _probe_cache[recording_id] = result
    _probe_cache.move_to_end(recording_id)
    while len(_probe_cache) > _PROBE_CACHE_MAX_ENTRIES:
        _probe_cache.popitem(last=False)


def _run_in_background(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _get_plugin(widget_id: str) -> HDHomeRunPlugin:
    return get_typed_plugin(widget_id, HDHomeRunPlugin, "HDHomeRun")


@router.get("/transcode-presets")
async def transcode_presets():
    # input_args/output_args are exposed (not just label/description) so the
    # settings UI can render a live command preview as the user changes
    # hwaccel/custom_ffmpeg_args, before saving — matching what
    # transcoding.command_preview() computes for the saved value.
    return [
        {
            "id": preset_id,
            "label": preset.label,
            "description": preset.description,
            "input_args": preset.input_args,
            "output_args": preset.output_args,
            "hardware": preset.hardware,
        }
        for preset_id, preset in transcoding.TRANSCODE_PRESETS.items()
    ]


async def _terminate(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=_FFMPEG_TERMINATE_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()


async def _terminate_and_release(process: asyncio.subprocess.Process) -> None:
    """Terminate a spawned ffmpeg process and free its `_ffmpeg_semaphore` slot.

    Every successful `_ffmpeg_semaphore.acquire()` for this process is paired
    with exactly one call to this (from the streaming generator's `finally`
    or a post-spawn failure path) so the slot is held for the transcode's
    whole lifetime, not just around the subprocess spawn.
    """
    try:
        await _terminate(process)
    finally:
        _ffmpeg_semaphore.release()


async def _drain_stderr(stderr: asyncio.StreamReader, tail: bytearray, done: asyncio.Event) -> None:
    # ffmpeg writes a steady trickle of log lines to stderr; if nothing reads
    # them, the OS pipe buffer eventually fills and ffmpeg blocks on write(),
    # silently stalling an otherwise-healthy stream. This keeps the pipe
    # drained for the process's whole lifetime, keeping only the last few KB
    # around — enough to explain a startup failure (bad channel, busy tuner).
    #
    # `done` is what makes that tail trustworthy. This runs as a detached
    # task, so when ffmpeg dies instantly the reader below can observe EOF on
    # *stdout* and build its error message before this task has had its first
    # turn on the event loop — leaving the tail empty and reporting "no error
    # message from ffmpeg" for a process that in fact explained itself in
    # detail. Callers wait on this event before reading `tail`.
    try:
        while True:
            chunk = await stderr.read(4096)
            if not chunk:
                return
            tail += chunk
            del tail[: max(0, len(tail) - _STDERR_TAIL_BYTES)]
    finally:
        done.set()


async def _describe_failure(
    process: asyncio.subprocess.Process,
    stderr_tail: bytearray,
    drain_done: asyncio.Event,
) -> tuple[str, str]:
    """Why ffmpeg produced nothing: a one-line cause, and its stderr output."""
    # Let the drain finish so the reason is built from complete stderr rather
    # than whatever happened to have been read by now.
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(drain_done.wait(), timeout=_STDERR_FLUSH_TIMEOUT_SECONDS)
    # And let the process be reaped, so `returncode` distinguishes "ffmpeg
    # died" from "ffmpeg is alive but produced nothing". Closing stdout is not
    # the same event as exiting, and `returncode` stays None until waited on.
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(process.wait(), timeout=_STDERR_FLUSH_TIMEOUT_SECONDS)

    if process.returncode is not None:
        cause = f"ffmpeg exited with code {process.returncode} before producing any output"
    else:
        cause = f"ffmpeg produced no output within {_FFMPEG_STARTUP_TIMEOUT_SECONDS}s and was still running"
    return cause, bytes(stderr_tail).decode(errors="replace").strip()


async def _describe_mid_stream_exit(
    process: asyncio.subprocess.Process,
    stderr_tail: bytearray,
    drain_done: asyncio.Event,
    widget_id: str,
    channel_number: str,
) -> None:
    """Log a stream that started successfully and then died on its own."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(process.wait(), timeout=_STDERR_FLUSH_TIMEOUT_SECONDS)
    if process.returncode in (None, 0):
        return
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(drain_done.wait(), timeout=_STDERR_FLUSH_TIMEOUT_SECONDS)
    logger.warning(
        "HDHomeRun widget '%s' channel %s: ffmpeg exited with code %s mid-stream\nffmpeg output:\n%s",
        widget_id,
        channel_number,
        process.returncode,
        bytes(stderr_tail).decode(errors="replace").strip() or "(none)",
    )


async def _probe_after_failure(settings: dict[str, Any]) -> dict[str, Any] | None:
    """Re-run the failed settings against a synthetic clip, or None if that couldn't be done.

    Separates "the GPU can't do this" from "the tuner was busy / the channel
    is dead", which the tuner-fed failure alone cannot distinguish. Bounded
    and never raising: this runs inside an already-failing request, so a slow
    or broken probe must not turn a clear 502 into a hang or a 500.
    """
    try:
        return await asyncio.wait_for(hwaccel.probe_transcode(settings), timeout=_FAILURE_PROBE_TIMEOUT_SECONDS)
    except TimeoutError:
        return None
    except Exception:
        logger.exception("Diagnostic test transcode failed to run")
        return None


@router.get("/{widget_id}/stream/{channel_number}")
async def stream_channel(widget_id: str, channel_number: str, request: Request):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    if not hdhomerun_client.is_tuner_configured(settings):
        raise HTTPException(status_code=404, detail="Tuner not configured")

    # channel_number is never taken from a client-supplied URL — only used
    # to build the tuner's own stream URL server-side, from settings the
    # user already saved. Reconstructing it this way (rather than trusting a
    # client-passed URL) avoids turning this into an open proxy.
    raw_url = hdhomerun_client.raw_stream_url(settings, channel_number)
    try:
        ffmpeg_args = transcoding.build_ffmpeg_args(settings, raw_url)
    except transcoding.InvalidCustomFfmpegArgsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preset_id = settings.get("hwaccel", transcoding.DEFAULT_PRESET)
    preset = transcoding.resolve_preset(preset_id)
    device = transcoding.resolve_device(settings)
    command = shlex.join(["ffmpeg", *ffmpeg_args])

    await _ffmpeg_semaphore.acquire()
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            *ffmpeg_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        _ffmpeg_semaphore.release()
        raise HTTPException(
            status_code=503,
            detail=(
                "ffmpeg is not installed or not on PATH for the backend process. "
                "If running the bare-metal installer, install it (e.g. `brew install ffmpeg` on macOS, "
                "`sudo apt install ffmpeg` on Debian/Raspberry Pi) and restart the backend. "
                "If running in Docker/Podman, ffmpeg must be present in the backend image itself — "
                "installing it on the container host has no effect; rebuild the backend image."
            ),
        ) from exc
    assert process.stdout is not None
    assert process.stderr is not None

    logger.info(
        "HDHomeRun widget '%s' channel %s: starting transcode (preset=%s, device=%s): %s",
        widget_id,
        channel_number,
        preset_id,
        device,
        command,
    )

    stderr_tail = bytearray()
    drain_done = asyncio.Event()
    _run_in_background(_drain_stderr(process.stderr, stderr_tail, drain_done))

    # A StreamingResponse commits its 200 status as soon as it starts, so any
    # ffmpeg failure (busy tuner, unreachable channel, bad input) has to
    # surface *before* that point — otherwise it degrades to a silent, empty
    # "successful" response with nothing playable in it. Give ffmpeg a
    # startup window to either produce its first chunk of output or fail.
    try:
        first_chunk = await asyncio.wait_for(
            process.stdout.read(_STREAM_CHUNK_BYTES), timeout=_FFMPEG_STARTUP_TIMEOUT_SECONDS
        )
    except TimeoutError:
        first_chunk = b""

    if not first_chunk:
        cause, reason = await _describe_failure(process, stderr_tail, drain_done)
        _run_in_background(_terminate_and_release(process))
        logger.error(
            "HDHomeRun widget '%s' channel %s: %s (preset=%s, device=%s)\ncommand: %s\nffmpeg output:\n%s",
            widget_id,
            channel_number,
            cause,
            preset_id,
            device,
            command,
            reason or "(none)",
        )

        detail = f"Could not start streaming channel {channel_number}: {cause}"
        if reason:
            detail += f". ffmpeg said: {reason[-_DETAIL_REASON_CHARS:]}"

        # A hardware preset that fails at startup is the case where the raw
        # stderr is least likely to be self-explanatory, and where the user
        # has the fewest ways to investigate (no shell in the container, no
        # spare tuner). Re-run the same arguments against a synthetic MPEG-2
        # clip at verbose logging, so the very first failure carries a real
        # explanation rather than requiring a second, manual round trip.
        if preset.hardware:
            probe = await _probe_after_failure(settings)
            if probe is not None:
                logger.error(
                    "HDHomeRun widget '%s': diagnostic test transcode with the same settings %s\ncommand: %s\n%s",
                    widget_id,
                    "succeeded (so the tuner or channel is the likely problem, not the GPU)"
                    if probe["ok"]
                    else "also failed",
                    probe.get("command"),
                    probe.get("output") or "(no output)",
                )
                if not probe["ok"] and probe.get("output"):
                    detail += (
                        " A test transcode with these same settings also failed, so this is a hardware-acceleration "
                        "problem rather than a tuner problem. Run the hardware acceleration diagnostics for details."
                    )
                elif probe["ok"]:
                    detail += (
                        " A test transcode with these same settings succeeded, so hardware acceleration is working — "
                        "the tuner or this channel is the more likely problem."
                    )

        raise HTTPException(status_code=502, detail=detail)

    async def body():
        try:
            yield first_chunk
            while True:
                # Actively re-check for disconnect on a bounded read timeout
                # instead of relying solely on Starlette to cancel this
                # generator when the client goes away — that cancellation
                # has proven unreliable in practice (observed ffmpeg
                # processes, and the physical tuner each one held, still
                # running tens of minutes after the client disconnected).
                if await request.is_disconnected():
                    break
                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(_STREAM_CHUNK_BYTES), timeout=_DISCONNECT_POLL_INTERVAL_SECONDS
                    )
                except TimeoutError:
                    continue
                if not chunk:
                    # EOF on stdout: ffmpeg is done. A clean exit is just the
                    # tuner-side stream ending, but a non-zero code here is a
                    # stream that started fine and then broke — the player
                    # only sees playback stop, so without this it leaves no
                    # trace anywhere.
                    await _describe_mid_stream_exit(process, stderr_tail, drain_done, widget_id, channel_number)
                    break
                yield chunk
        finally:
            # Run on an independent task rather than awaiting inline: if
            # this generator is being torn down because its own task was
            # cancelled (the client-disconnect case), awaiting anything
            # directly here would be cancelled too, before ffmpeg is
            # actually reaped and the tuner released.
            _run_in_background(_terminate_and_release(process))

    return StreamingResponse(body(), media_type="video/mp2t")


@router.get("/{widget_id}/hwaccel-diagnostics", dependencies=[Depends(get_current_admin)])
async def hwaccel_diagnostics(widget_id: str, device: str | None = None):
    """Probe every link in the hardware-acceleration chain and report back.

    Admin-only despite the router's user-level dependency: this exposes host
    hardware detail, device permissions and the backend's uid/gid.

    Takes ~2-15s (it test-encodes a short clip through each plausible preset),
    which is why it's an explicit request rather than part of the widget's
    detail payload.
    """
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    report = await hwaccel.full_report(
        device or transcoding.resolve_device(settings),
        extra_settings={
            "hwaccel": settings.get("hwaccel", transcoding.DEFAULT_PRESET),
            "custom_ffmpeg_args": settings.get("custom_ffmpeg_args", ""),
        },
    )
    # Also to the log, so a user reporting a bug can paste `docker compose
    # logs backend` instead of having to re-run this against a cookie.
    logger.info(
        "HDHomeRun widget '%s': hardware acceleration diagnostics for %s\n%s",
        widget_id,
        report["device"],
        "\n".join(report["summary"]) or "(no findings)",
    )
    return report


@router.get("/{widget_id}/playlist/{channel_number}")
async def channel_playlist(widget_id: str, channel_number: str):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    if not hdhomerun_client.is_tuner_configured(settings):
        raise HTTPException(status_code=404, detail="Tuner not configured")

    raw_url = hdhomerun_client.raw_stream_url(settings, channel_number)
    playlist = f"#EXTM3U\n#EXTINF:-1,{channel_number}\n{raw_url}\n"
    return Response(
        content=playlist,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": f'inline; filename="{channel_number}.m3u"'},
    )


class RecordingRuleCreateRequest(BaseModel):
    series_id: str | None = None
    date_time: int | None = None
    channel: str | None = None
    recent_only: bool | None = None
    start_padding: int | None = None
    end_padding: int | None = None


@router.get("/{widget_id}/guide")
async def handle_get_guide(widget_id: str):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    guide = await hdhomerun_client.fetch_full_guide(settings, widget_id)
    if guide is None:
        return []
    return guide


@router.post("/{widget_id}/recording-rules")
async def handle_create_recording_rule(widget_id: str, payload: RecordingRuleCreateRequest):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    try:
        rules = await hdhomerun_client.add_recording_rule(settings, payload.model_dump())
        return rules
    except hdhomerun_client.HDHomeRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{widget_id}/recording-rules/{rule_id}")
async def handle_delete_recording_rule(widget_id: str, rule_id: str):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    try:
        rules = await hdhomerun_client.delete_recording_rule(settings, rule_id)
        return rules
    except hdhomerun_client.HDHomeRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{widget_id}/recording-stream")
async def handle_stream_recording(
    widget_id: str, url: str, request: Request, start: float | None = None, audio_index: int | None = None
):
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    target_url = hdhomerun_client.resolve_recording_url(settings, url)

    mode = settings.get("playback_mode", "server_transcode")
    if mode == "server_transcode":
        try:
            ffmpeg_args = transcoding.build_ffmpeg_args(
                settings, target_url, seek_seconds=start, audio_index=audio_index
            )
        except transcoding.InvalidCustomFfmpegArgsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        preset_id = settings.get("hwaccel", transcoding.DEFAULT_PRESET)
        device = transcoding.resolve_device(settings)
        command = shlex.join(["ffmpeg", *ffmpeg_args])

        await _ffmpeg_semaphore.acquire()
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                *ffmpeg_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            _ffmpeg_semaphore.release()
            raise HTTPException(status_code=503, detail="ffmpeg is not installed on PATH") from exc

        assert process.stdout is not None
        assert process.stderr is not None

        logger.info(
            "HDHomeRun widget '%s': starting recording transcode for %s (preset=%s, device=%s): %s",
            widget_id,
            target_url,
            preset_id,
            device,
            command,
        )

        stderr_tail = bytearray()
        drain_done = asyncio.Event()
        _run_in_background(_drain_stderr(process.stderr, stderr_tail, drain_done))

        try:
            first_chunk = await asyncio.wait_for(
                process.stdout.read(_STREAM_CHUNK_BYTES), timeout=_FFMPEG_STARTUP_TIMEOUT_SECONDS
            )
        except TimeoutError:
            first_chunk = b""

        if not first_chunk:
            cause, reason = await _describe_failure(process, stderr_tail, drain_done)
            _run_in_background(_terminate_and_release(process))
            logger.error(
                "HDHomeRun widget '%s': recording transcode failed for %s: %s\nffmpeg output:\n%s",
                widget_id,
                target_url,
                cause,
                reason or "(none)",
            )
            if "503" in reason or "Service Unavailable" in reason:
                detail = (
                    "All hardware tuner units on the HDHomeRun device are currently busy "
                    "(HTTP 503 Service Unavailable)."
                )
            else:
                detail = f"Could not start streaming recording: {cause}"
                if reason:
                    detail += f". ffmpeg said: {reason[-_DETAIL_REASON_CHARS:]}"
            raise HTTPException(status_code=502, detail=detail)

        async def transcode_generator():
            try:
                yield first_chunk
                while True:
                    # Same rationale as stream_channel.body(): actively poll
                    # for client disconnect on a bounded read timeout instead
                    # of relying solely on Starlette's cancel-on-disconnect,
                    # which has proven unreliable in practice. Without this,
                    # a dropped client leaves ffmpeg (and this transcode's
                    # _ffmpeg_semaphore slot, capacity 2) running/held
                    # indefinitely, since nothing else here can ever return
                    # from process.stdout.read() or reach the `finally`.
                    if await request.is_disconnected():
                        break
                    try:
                        chunk = await asyncio.wait_for(
                            process.stdout.read(_STREAM_CHUNK_BYTES), timeout=_DISCONNECT_POLL_INTERVAL_SECONDS
                        )
                    except TimeoutError:
                        continue
                    if not chunk:
                        break
                    yield chunk
            finally:
                _run_in_background(_terminate_and_release(process))

        return StreamingResponse(
            transcode_generator(),
            media_type="video/mp2t",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # Fallback raw stream proxy
    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream("GET", target_url) as resp:
                    if resp.status_code >= 400:
                        yield b""
                        return
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        yield chunk
        except Exception as exc:
            logger.debug("Recording stream proxy error from %s: %s", target_url, exc)
            yield b""

    return StreamingResponse(stream_generator(), media_type="video/mp2t")


@router.get("/{widget_id}/recording-detail")
async def handle_recording_detail(
    widget_id: str,
    url: str,
    recording_id: str,
    start: float | None = None,
    record_end: float | None = None,
):
    """Duration/stream metadata driving the recordings player's scrub bar and menus.

    In-progress recordings (no record_end yet, or one still in the future)
    skip ffprobe entirely - the file is still being written, so probing it
    is unreliable - and report an elapsed-time duration instead that grows
    each time the player re-polls this route.
    """
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]

    if record_end is None or record_end > time.time():
        return {
            "is_in_progress": True,
            "duration_seconds": max(0.0, time.time() - start) if start is not None else None,
            "video": None,
            "audio": [],
            "has_captions": False,
        }

    if recording_id not in _probe_cache:
        target_url = hdhomerun_client.resolve_recording_url(settings, url)
        result = await media_probe.probe(target_url)
        _probe_cache_set(
            recording_id,
            result
            or {
                "duration_seconds": (record_end - start) if start is not None else None,
                "video": None,
                "audio": [],
                "has_captions": False,
            },
        )

    return {"is_in_progress": False, **_probe_cache[recording_id]}


@router.get("/{widget_id}/recording-captions.vtt")
async def handle_recording_captions(widget_id: str, url: str, recording_id: str, record_end: float | None = None):
    if record_end is None or record_end > time.time():
        raise HTTPException(status_code=404, detail="Captions are only available for completed recordings")

    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    target_url = hdhomerun_client.resolve_recording_url(settings, url)

    vtt_path = await media_cache.generate_captions_vtt(target_url, recording_id)
    if vtt_path is None:
        raise HTTPException(status_code=404, detail="No closed captions found for this recording")
    return FileResponse(vtt_path, media_type="text/vtt")


def _thumbnails_enabled(settings: dict[str, Any]) -> bool:
    return bool(settings.get("thumbnails_enabled", True))


async def _resolved_thumbnail_sprite(
    widget_id: str, recording_id: str, url: str, record_end: float | None
) -> tuple[str, str]:
    """Shared validation/lookup for the sprite .jpg and .vtt routes below."""
    plugin = _get_plugin(widget_id)
    settings = plugin.config["settings"]
    if not _thumbnails_enabled(settings):
        raise HTTPException(status_code=404, detail="Thumbnail previews are disabled for this widget")
    if record_end is None or record_end > time.time():
        raise HTTPException(status_code=404, detail="Thumbnails are only available for completed recordings")

    target_url = hdhomerun_client.resolve_recording_url(settings, url)
    duration = await _resolved_duration(target_url, recording_id)
    if duration is None:
        raise HTTPException(status_code=404, detail="Could not determine recording duration")

    sprite = await media_cache.generate_thumbnail_sprite(target_url, recording_id, duration)
    if sprite is None:
        raise HTTPException(status_code=404, detail="Could not generate thumbnail preview")
    return sprite


@router.get("/{widget_id}/recording-thumbnails/{recording_id}.jpg")
async def handle_recording_thumbnail_sprite(
    widget_id: str, recording_id: str, url: str, record_end: float | None = None
):
    sprite = await _resolved_thumbnail_sprite(widget_id, recording_id, url, record_end)
    return FileResponse(sprite[0], media_type="image/jpeg")


@router.get("/{widget_id}/recording-thumbnails/{recording_id}.vtt")
async def handle_recording_thumbnail_vtt(widget_id: str, recording_id: str, url: str, record_end: float | None = None):
    sprite = await _resolved_thumbnail_sprite(widget_id, recording_id, url, record_end)
    return FileResponse(sprite[1], media_type="text/vtt")


async def _resolved_duration(target_url: str, recording_id: str) -> float | None:
    """The best known duration for a completed recording, probing (and caching) if needed."""
    if recording_id not in _probe_cache:
        result = await media_probe.probe(target_url)
        if result is not None:
            _probe_cache_set(recording_id, result)
    cached = _probe_cache.get(recording_id)
    if cached and cached.get("duration_seconds"):
        return cached["duration_seconds"]
    return None
