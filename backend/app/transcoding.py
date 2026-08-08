"""ffmpeg transcode presets for HDHomeRun `server_transcode` playback.

Turning the tuner's raw MPEG-2 stream into browser-playable H.264/AAC needs
`ffmpeg`, and the fastest way to do that depends entirely on what hardware
the *backend* happens to run on — a software encode that's fine on a
desktop CPU can pin a Raspberry Pi, a hardware encoder that's free on one
box (Intel Quick Sync) doesn't exist on another (Apple Silicon, a plain ARM
SBC), and there's no single "auto-detect" ffmpeg build/driver setup that
covers all of them. The presets below cover the combinations this project
is actually deployed on or tested against; "custom" is the escape hatch for
anything else (a different GPU, a tuned bitrate, etc).

Each preset splits into `input_args` (placed before `-i`, needed for
hwaccel decode setup) and `output_args` (placed after it, before the fixed
`-f mpegts pipe:1` framing that the /stream route always appends — the
container and transport are structural, not something a preset should be
able to change).
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any

DEFAULT_PRESET = "software"


class InvalidCustomFfmpegArgsError(ValueError):
    """A saved `custom_ffmpeg_args` string couldn't be parsed as shell-style
    arguments (e.g. an unbalanced quote) — lets callers turn this into a
    clean 400 instead of a raw `shlex` `ValueError`/crash reaching the user.
    """


@dataclass(frozen=True)
class TranscodePreset:
    label: str
    description: str
    input_args: list[str] = field(default_factory=list)
    output_args: list[str] = field(default_factory=list)


TRANSCODE_PRESETS: dict[str, TranscodePreset] = {
    "software": TranscodePreset(
        label="Software (libx264)",
        description=(
            "CPU-only encode — works on any machine and is the safe default, "
            "at the cost of real CPU load per concurrent viewer."
        ),
        # -ac 2: ATSC OTA audio is commonly 5.1 (6-channel) AC-3. ffmpeg's aac
        # encoder happily passes the channel count through, but browsers'
        # MSE AAC decoders only reliably support stereo — appending a
        # 6-channel AAC init segment gets silently rejected by the
        # SourceBuffer (a MediaSource-ending error with no ERROR event from
        # the player library), producing a blank video despite a healthy 200
        # response and real bytes flowing. Confirmed against a real
        # HDHomeRun tuner via mpegts.js's SourceBuffer error trace.
        output_args=["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ac", "2"],
    ),
    "software_lowpower": TranscodePreset(
        label="Software, low-power (for Raspberry Pi / ARM SBCs)",
        description=(
            "Still CPU-only, but tuned for weak ARM boards: ffmpeg has no "
            "reliable hardware H.264 *encoder* for the Raspberry Pi (its GPU "
            "only accelerates decode), so this trades bitrate efficiency for "
            "much less CPU per frame via preset=ultrafast."
        ),
        output_args=[
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-c:a",
            "aac",
            "-ac",
            "2",
        ],
    ),
    "videotoolbox": TranscodePreset(
        label="Apple VideoToolbox (macOS)",
        description="Hardware encode on macOS — Intel or Apple Silicon — e.g. running the backend on a Mac/MacBook.",
        # a53cc (embedding the source's ATSC closed-caption SEI into the
        # output) defaults to on and reliably crashes ffmpeg's VideoToolbox
        # encoder wrapper on OTA streams that carry CEA-608/708 captions —
        # confirmed against a real HDHomeRun tuner: with it left on, ffmpeg
        # runs and audio flows, but zero video frames ever get encoded
        # (silent black/frozen playback despite a 200 response). Disabling
        # it just drops caption passthrough; the picture is unaffected.
        #
        # -profile:v high -level 4.0: without an explicit level, the
        # VideoToolbox wrapper signals Level 3.1 even when actually encoding
        # 720p59.94 content, which needs Level 4.0+ (3.1's macroblock/sec
        # budget doesn't cover 720p at 60fps) — a non-conformant bitstream
        # that browsers can demux fine (so the network tab looks healthy)
        # but silently fail to decode frames from. Forcing 4.0 covers every
        # ATSC OTA resolution/frame-rate combination in practice (up to
        # 1080i/p at 30fps, or 720p at 60fps).
        output_args=[
            "-c:v",
            "h264_videotoolbox",
            "-a53cc",
            "0",
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-b:v",
            "6M",
            "-c:a",
            "aac",
            "-ac",
            "2",
        ],
    ),
    "qsv": TranscodePreset(
        label="Intel Quick Sync Video",
        description=(
            "Hardware decode+encode on Intel CPUs with an iGPU, on Linux with "
            "the intel-media-driver installed and /dev/dri accessible to the "
            "backend process. The Docker image already bundles the driver "
            "(see backend/Dockerfile); on Docker Compose you still need to "
            "uncomment the /dev/dri passthrough in docker-compose.yml."
        ),
        input_args=["-qsv_device", "/dev/dri/renderD128", "-hwaccel", "qsv", "-hwaccel_output_format", "qsv"],
        output_args=["-c:v", "h264_qsv", "-preset", "veryfast", "-c:a", "aac", "-ac", "2"],
    ),
    "vaapi": TranscodePreset(
        label="VAAPI (Intel/AMD, Linux)",
        description=(
            "Hardware encode via VAAPI on Linux — Intel iGPUs or AMD GPUs "
            'with Mesa drivers. Assumes /dev/dri/renderD128; use "Custom" '
            "if your render device path differs. The Docker image already "
            "bundles the driver (see backend/Dockerfile); on Docker Compose "
            "you still need to uncomment the /dev/dri passthrough in "
            "docker-compose.yml."
        ),
        input_args=["-vaapi_device", "/dev/dri/renderD128", "-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"],
        output_args=["-c:v", "h264_vaapi", "-c:a", "aac", "-ac", "2"],
    ),
    "nvenc": TranscodePreset(
        label="NVIDIA NVENC",
        description="Hardware encode on machines with an NVIDIA GPU and current drivers installed.",
        input_args=["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"],
        output_args=["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "ll", "-c:a", "aac", "-ac", "2"],
    ),
    "custom": TranscodePreset(
        label="Custom",
        description=(
            "Full manual control — raw ffmpeg arguments, inserted between "
            '"-i <stream>" and the fixed output framing. Falls back to the '
            "Software preset if left blank."
        ),
    ),
}


def resolve_preset(hwaccel: str) -> TranscodePreset:
    return TRANSCODE_PRESETS.get(hwaccel, TRANSCODE_PRESETS[DEFAULT_PRESET])


def _output_args(settings: dict[str, Any]) -> list[str]:
    hwaccel = settings.get("hwaccel", DEFAULT_PRESET)
    if hwaccel == "custom":
        raw = settings.get("custom_ffmpeg_args", "") or ""
        try:
            custom = shlex.split(raw)
        except ValueError as exc:
            raise InvalidCustomFfmpegArgsError(f"Invalid custom ffmpeg arguments: {exc}") from exc
        return custom or TRANSCODE_PRESETS[DEFAULT_PRESET].output_args
    return resolve_preset(hwaccel).output_args


def build_ffmpeg_args(settings: dict[str, Any], input_url: str) -> list[str]:
    """Full ffmpeg arg list (excluding the "ffmpeg" program name itself)."""
    preset = resolve_preset(settings.get("hwaccel", DEFAULT_PRESET))
    return [
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostats",
        *preset.input_args,
        "-i",
        input_url,
        *_output_args(settings),
        "-f",
        "mpegts",
        "pipe:1",
    ]


def command_preview(settings: dict[str, Any], stream_placeholder: str = "<channel stream>") -> str:
    """The exact command `/stream` will run, for display in the UI.

    Degrades to an inline error message instead of raising when
    custom_ffmpeg_args is unparseable — this is called unconditionally while
    rendering the widget's summary/detail (see
    HDHomeRunPlugin._settings_view), so raising here would take down the
    whole widget over a typo in a field the user hasn't gotten to fix yet.
    """
    try:
        args = build_ffmpeg_args(settings, stream_placeholder)
    except InvalidCustomFfmpegArgsError as exc:
        return f"<invalid custom ffmpeg arguments: {exc}>"
    return shlex.join(["ffmpeg", *args])
