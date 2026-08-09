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
from collections.abc import Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app import transcoding
from app.auth import get_current_user
from app.integrations import hdhomerun_client
from app.plugins.base import registry
from app.plugins.hdhomerun.plugin import HDHomeRunPlugin

router = APIRouter(prefix="/api/hdhomerun", tags=["hdhomerun"], dependencies=[Depends(get_current_user)])

_STREAM_CHUNK_BYTES = 64 * 1024
_FFMPEG_STARTUP_TIMEOUT_SECONDS = 8
_FFMPEG_TERMINATE_TIMEOUT_SECONDS = 5
_DISCONNECT_POLL_INTERVAL_SECONDS = 1
_STDERR_TAIL_BYTES = 4000

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


async def _drain_stderr(stderr: asyncio.StreamReader, tail: bytearray) -> None:
    # ffmpeg writes a steady trickle of log lines to stderr; if nothing reads
    # them, the OS pipe buffer eventually fills and ffmpeg blocks on write(),
    # silently stalling an otherwise-healthy stream. This keeps the pipe
    # drained for the process's whole lifetime, keeping only the last few KB
    # around — enough to explain a startup failure (bad channel, busy tuner).
    while True:
        chunk = await stderr.read(4096)
        if not chunk:
            return
        tail += chunk
        del tail[: max(0, len(tail) - _STDERR_TAIL_BYTES)]


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

    stderr_tail = bytearray()
    _run_in_background(_drain_stderr(process.stderr, stderr_tail))

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
        _run_in_background(_terminate(process))
        reason = bytes(stderr_tail).decode(errors="replace").strip()
        detail = f"ffmpeg failed to start streaming channel {channel_number}"
        detail += f": {reason[-500:]}" if reason else " (no output and no error message from ffmpeg)"
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
