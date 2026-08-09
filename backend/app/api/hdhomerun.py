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
from collections.abc import Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app import hwaccel, transcoding
from app.auth import get_current_admin, get_current_user
from app.integrations import hdhomerun_client
from app.plugins.base import registry
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


def _run_in_background(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _get_plugin(widget_id: str) -> HDHomeRunPlugin:
    plugin = registry.get(widget_id)
    if not isinstance(plugin, HDHomeRunPlugin):
        raise HTTPException(status_code=404, detail=f"Unknown HDHomeRun widget '{widget_id}'")
    return plugin


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

    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            *ffmpeg_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
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
        _run_in_background(_terminate(process))
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
            _run_in_background(_terminate(process))

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
