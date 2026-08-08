from __future__ import annotations

import time

import httpx
import respx

from app.plugins.hdhomerun.plugin import HDHomeRunPlugin

LINEUP_RESPONSE = [
    {"GuideNumber": "4.1", "GuideName": "WCMH-DT", "HD": 1, "URL": "http://hdhr.local:5004/auto/v4.1"},
]
DISCOVER_RESPONSE = {
    "FriendlyName": "HDHomeRun FLEX 4K",
    "ModelNumber": "HDFX-4K",
    "FirmwareVersion": "20260326",
    "DeviceAuth": "sometoken",
    "TunerCount": 4,
}


def make_plugin(**settings) -> HDHomeRunPlugin:
    return HDHomeRunPlugin({"id": "hdhomerun", "settings": {**HDHomeRunPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["tuner_connected"] is False
    assert summary["dvr_connected"] is False
    assert summary["channel_count"] == 0
    assert summary["guide_available"] is False
    assert summary["now_playing"] == []
    assert summary["active_recordings_count"] == 0


async def test_get_summary_echoes_settings():
    plugin = make_plugin(tuner_host="hdhr.local", dvr_host="dvr.local", epg_url="http://epg.example/guide.xml")

    summary = await plugin.get_summary()

    assert summary["tuner_host"] == "hdhr.local"
    assert summary["dvr_host"] == "dvr.local"
    assert summary["epg_url"] == "http://epg.example/guide.xml"


async def test_get_summary_defaults_hwaccel_to_software_and_exposes_command():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["hwaccel"] == "software"
    assert summary["custom_ffmpeg_args"] == ""
    assert summary["ffmpeg_command"].startswith("ffmpeg ")
    assert "libx264" in summary["ffmpeg_command"]


async def test_get_summary_reflects_custom_hwaccel_in_ffmpeg_command():
    plugin = make_plugin(hwaccel="custom", custom_ffmpeg_args="-c:v h264_v4l2m2m -c:a aac")

    summary = await plugin.get_summary()

    assert "h264_v4l2m2m" in summary["ffmpeg_command"]


async def test_get_summary_survives_unparseable_custom_ffmpeg_args():
    # Regression test: a saved custom_ffmpeg_args typo (e.g. an unbalanced
    # quote) must not crash the whole widget just from viewing its summary
    # (which unconditionally builds a command preview) — see
    # transcoding.command_preview.
    plugin = make_plugin(hwaccel="custom", custom_ffmpeg_args='-c:v "libx264')

    summary = await plugin.get_summary()

    assert "invalid custom ffmpeg arguments" in summary["ffmpeg_command"].lower()


@respx.mock
async def test_get_summary_connected_reports_channel_count_no_guide():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun"})
    )
    plugin = make_plugin(tuner_host="hdhr.local")

    summary = await plugin.get_summary()

    assert summary["tuner_connected"] is True
    assert summary["channel_count"] == 1
    assert summary["guide_available"] is False
    assert summary["now_playing"] == []


@respx.mock
async def test_get_summary_includes_now_playing_when_guide_available():
    now = time.time()
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "GuideNumber": "4.1",
                    "Guide": [{"StartTime": now - 10, "EndTime": now + 10, "Title": "Local News"}],
                }
            ],
        )
    )
    plugin = make_plugin(tuner_host="hdhr.local")

    summary = await plugin.get_summary()

    assert summary["guide_available"] is True
    assert summary["now_playing"] == [
        {"channel_number": "4.1", "channel_name": "WCMH-DT", "title": "Local News", "episode_title": None}
    ]


@respx.mock
async def test_get_summary_degrades_gracefully_on_tuner_connection_error():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(500))
    plugin = make_plugin(tuner_host="hdhr.local")

    summary = await plugin.get_summary()

    assert summary["tuner_connected"] is True
    assert summary["channel_count"] == 0


@respx.mock
async def test_get_detail_populates_channels_tuners_and_dvr():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://hdhr.local:80/status.json").mock(
        return_value=httpx.Response(200, json=[{"VctNumber": "4.1", "SignalStrengthPercent": 95}])
    )
    respx.get("http://dvr.local:59090/discover.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "FriendlyName": "HDHomeRun RECORD",
                "Version": "1",
                "FreeSpace": 100,
                "StorageURL": "http://dvr.local:59090/recorded_files.json",
            },
        )
    )
    respx.get("http://dvr.local:59090/recorded_files.json").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://dvr.local:59090/recording_rules.json").mock(return_value=httpx.Response(200, json=[]))
    plugin = make_plugin(tuner_host="hdhr.local", dvr_host="dvr.local")

    detail = await plugin.get_detail()

    assert detail["tuner_info"]["friendly_name"] == "HDHomeRun FLEX 4K"
    assert len(detail["channels"]) == 1
    assert detail["tuners"][0]["signal_strength_percent"] == 95
    assert detail["dvr_info"]["friendly_name"] == "HDHomeRun RECORD"
    assert detail["recordings_in_progress"] == []
    assert detail["upcoming_recording_rules_count"] == 0


@respx.mock
async def test_channels_playback_url_server_transcode():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://hdhr.local:80/status.json").mock(return_value=httpx.Response(200, json=[]))
    plugin = make_plugin(tuner_host="hdhr.local", playback_mode="server_transcode")

    detail = await plugin.get_detail()

    assert detail["channels"][0]["playback_url"] == "/api/hdhomerun/hdhomerun/stream/4.1"


@respx.mock
async def test_channels_playback_url_external_is_none():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://hdhr.local:80/status.json").mock(return_value=httpx.Response(200, json=[]))
    plugin = make_plugin(tuner_host="hdhr.local", playback_mode="external")

    detail = await plugin.get_detail()

    assert detail["channels"][0]["playback_url"] is None


async def test_get_detail_dvr_fields_empty_when_dvr_not_configured():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["dvr_connected"] is False
    assert detail["dvr_info"] is None
    assert detail["recordings_in_progress"] == []
    assert detail["upcoming_recording_rules_count"] == 0


@respx.mock
async def test_recordings_in_progress_filters_by_future_record_end():
    now = time.time()
    respx.get("http://dvr.local:59090/discover.json").mock(
        return_value=httpx.Response(
            200, json={"FriendlyName": "HDHomeRun RECORD", "StorageURL": "http://dvr.local:59090/recorded_files.json"}
        )
    )
    respx.get("http://dvr.local:59090/recorded_files.json").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"Title": "In Progress", "RecordEndTime": now + 100},
                {"Title": "Finished", "RecordEndTime": now - 100},
                {"Title": "Unknown"},
            ],
        )
    )
    plugin = make_plugin(dvr_host="dvr.local")

    summary = await plugin.get_summary()

    assert summary["active_recordings_count"] == 1


@respx.mock
async def test_get_summary_now_playing_filtered_by_favorites():
    now = time.time()
    respx.get("http://hdhr.local:80/lineup.json").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"GuideNumber": "4.1", "GuideName": "WCMH-DT", "URL": "http://hdhr.local:5004/auto/v4.1"},
                {"GuideNumber": "7.1", "GuideName": "WHIO-DT", "URL": "http://hdhr.local:5004/auto/v7.1"},
            ],
        )
    )
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"GuideNumber": "4.1", "Guide": [{"StartTime": now - 10, "EndTime": now + 10, "Title": "News"}]},
                {"GuideNumber": "7.1", "Guide": [{"StartTime": now - 10, "EndTime": now + 10, "Title": "Weather"}]},
            ],
        )
    )
    plugin = make_plugin(tuner_host="hdhr.local", favorite_channels=["7.1"])

    summary = await plugin.get_summary()

    assert summary["channel_count"] == 2
    assert [entry["channel_number"] for entry in summary["now_playing"]] == ["7.1"]
    assert summary["favorite_channels"] == ["7.1"]


@respx.mock
async def test_get_summary_now_playing_not_capped_when_more_than_three_favorites():
    now = time.time()
    channel_numbers = ["2.1", "4.1", "7.1", "9.1"]
    respx.get("http://hdhr.local:80/lineup.json").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"GuideNumber": n, "GuideName": f"CH{n}", "URL": f"http://hdhr.local:5004/auto/v{n}"}
                for n in channel_numbers
            ],
        )
    )
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"GuideNumber": n, "Guide": [{"StartTime": now - 10, "EndTime": now + 10, "Title": f"Show {n}"}]}
                for n in channel_numbers
            ],
        )
    )
    plugin = make_plugin(tuner_host="hdhr.local", favorite_channels=channel_numbers)

    summary = await plugin.get_summary()

    assert [entry["channel_number"] for entry in summary["now_playing"]] == channel_numbers


async def test_get_ai_tools_returns_two_tools():
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert {t.name for t in tools} == {"get_now_playing", "get_active_recordings"}


@respx.mock
async def test_get_now_playing_tool_filters_by_channel():
    now = time.time()
    respx.get("http://hdhr.local:80/lineup.json").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"GuideNumber": "4.1", "GuideName": "WCMH-DT", "URL": "http://hdhr.local:5004/auto/v4.1"},
                {"GuideNumber": "7.1", "GuideName": "WHIO-DT", "URL": "http://hdhr.local:5004/auto/v7.1"},
            ],
        )
    )
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(
        return_value=httpx.Response(
            200,
            json=[{"GuideNumber": "4.1", "Guide": [{"StartTime": now - 10, "EndTime": now + 10, "Title": "News"}]}],
        )
    )
    respx.get("http://hdhr.local:80/status.json").mock(return_value=httpx.Response(200, json=[]))
    plugin = make_plugin(tuner_host="hdhr.local")
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["get_now_playing"].handler(channel="4.1")

    assert len(result["channels"]) == 1
    assert result["channels"][0]["now"]["title"] == "News"


async def test_get_active_recordings_tool_reports_not_connected():
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["get_active_recordings"].handler()

    assert result["dvr_connected"] is False
    assert result["recordings_in_progress"] == []
