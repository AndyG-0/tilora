from __future__ import annotations

from app import transcoding


def test_build_ffmpeg_args_defaults_to_software_preset():
    args = transcoding.build_ffmpeg_args({}, "http://tuner/stream")

    assert args == [
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostats",
        "-i",
        "http://tuner/stream",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-f",
        "mpegts",
        "pipe:1",
    ]


def test_build_ffmpeg_args_unknown_hwaccel_falls_back_to_software():
    args = transcoding.build_ffmpeg_args({"hwaccel": "not-a-real-preset"}, "url")

    assert args == transcoding.build_ffmpeg_args({"hwaccel": "software"}, "url")


def test_build_ffmpeg_args_includes_hwaccel_input_args():
    args = transcoding.build_ffmpeg_args({"hwaccel": "vaapi"}, "url")

    assert "-vaapi_device" in args
    assert "/dev/dri/renderD128" in args
    assert "h264_vaapi" in args
    # input args (hwaccel setup) must come before -i, output args after
    assert args.index("-vaapi_device") < args.index("-i")
    assert args.index("h264_vaapi") > args.index("-i")


def test_build_ffmpeg_args_custom_uses_raw_args():
    args = transcoding.build_ffmpeg_args(
        {"hwaccel": "custom", "custom_ffmpeg_args": "-c:v h264_v4l2m2m -b:v 4M -c:a aac"}, "url"
    )

    assert "-c:v" in args
    assert "h264_v4l2m2m" in args
    assert "-b:v" in args
    assert "4M" in args


def test_build_ffmpeg_args_custom_blank_falls_back_to_software_output_args():
    args = transcoding.build_ffmpeg_args({"hwaccel": "custom", "custom_ffmpeg_args": ""}, "url")

    assert args == transcoding.build_ffmpeg_args({"hwaccel": "software"}, "url")


def test_command_preview_uses_placeholder_and_ffmpeg_prefix():
    preview = transcoding.command_preview({"hwaccel": "software"})

    assert preview.startswith("ffmpeg ")
    assert "<channel stream>" in preview


def test_all_presets_produce_valid_arg_lists():
    for preset_id in transcoding.TRANSCODE_PRESETS:
        args = transcoding.build_ffmpeg_args({"hwaccel": preset_id}, "url")
        assert "-i" in args
        assert args[-3:] == ["-f", "mpegts", "pipe:1"]


def test_videotoolbox_disables_a53cc():
    # Regression test: ffmpeg's h264_videotoolbox encoder crashes (silently
    # encodes zero video frames, audio-only output) when a53cc is left at
    # its default of on and the source carries ATSC closed-caption SEI data
    # — confirmed against a real HDHomeRun OTA tuner. See the preset's
    # comment in app/transcoding.py for the reproduction.
    args = transcoding.build_ffmpeg_args({"hwaccel": "videotoolbox"}, "url")

    assert args[args.index("-a53cc") + 1] == "0"


def test_videotoolbox_forces_level_4_0():
    # Regression test: without an explicit level, h264_videotoolbox signals
    # Level 3.1 even when actually encoding 720p59.94 content, which needs
    # Level 4.0+ (3.1's macroblock/sec budget doesn't cover 720p60). Browsers
    # can demux the resulting non-conformant bitstream fine but silently fail
    # to decode any frames from it. See the preset's comment in
    # app/transcoding.py for the reproduction.
    args = transcoding.build_ffmpeg_args({"hwaccel": "videotoolbox"}, "url")

    assert args[args.index("-level") + 1] == "4.0"
    assert args[args.index("-profile:v") + 1] == "high"


def test_all_hwaccel_presets_force_stereo_audio():
    # Regression test: ATSC OTA audio is commonly 5.1 (6-channel) AC-3, and
    # ffmpeg's aac encoder passes the channel count through by default.
    # Browsers' MSE AAC decoders only reliably support stereo, so a
    # 6-channel AAC init segment gets silently rejected by the
    # SourceBuffer (MediaSource ends with no ERROR event from the player
    # library) — a blank video despite a healthy 200 response and real
    # bytes flowing. Confirmed against a real HDHomeRun tuner. "custom" is
    # exempt since it's raw user-supplied args.
    for preset_id, preset in transcoding.TRANSCODE_PRESETS.items():
        if preset_id == "custom":
            continue
        assert "-ac" in preset.output_args, preset_id
        assert preset.output_args[preset.output_args.index("-ac") + 1] == "2", preset_id
