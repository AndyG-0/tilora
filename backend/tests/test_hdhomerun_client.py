from __future__ import annotations

import time

import httpx
import pytest
import respx

from app.integrations import hdhomerun_client
from app.storage.cache import cache

TUNER_SETTINGS = {"tuner_host": "hdhr.local", "tuner_port": 80, "dvr_host": "", "dvr_port": 59090}
DVR_SETTINGS = {**TUNER_SETTINGS, "dvr_host": "dvr.local", "dvr_port": 59090}

DISCOVER_RESPONSE = {
    "FriendlyName": "HDHomeRun FLEX 4K",
    "ModelNumber": "HDFX-4K",
    "FirmwareVersion": "20260326",
    "DeviceID": "10AFFFFF",
    "DeviceAuth": "sometoken",
    "LineupURL": "http://hdhr.local/lineup.json",
    "TunerCount": 4,
}

LINEUP_RESPONSE = [
    {"GuideNumber": "4.1", "GuideName": "WCMH-DT", "HD": 1, "URL": "http://hdhr.local:5004/auto/v4.1"},
    {"GuideNumber": "7.1", "GuideName": "WHIO-DT", "Tags": "drm", "URL": "http://hdhr.local:5004/auto/v7.1"},
]


def test_is_tuner_configured_true_with_host():
    assert hdhomerun_client.is_tuner_configured(TUNER_SETTINGS)


def test_is_tuner_configured_false_without_host():
    assert not hdhomerun_client.is_tuner_configured({"tuner_host": ""})


def test_is_dvr_configured_true_with_host():
    assert hdhomerun_client.is_dvr_configured(DVR_SETTINGS)


def test_is_dvr_configured_false_without_host():
    assert not hdhomerun_client.is_dvr_configured(TUNER_SETTINGS)


@respx.mock
async def test_fetch_discover_returns_json():
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))

    result = await hdhomerun_client.fetch_discover(TUNER_SETTINGS)

    assert result["FriendlyName"] == "HDHomeRun FLEX 4K"


@respx.mock
async def test_fetch_discover_raises_on_error():
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(500))

    with pytest.raises(hdhomerun_client.HDHomeRunError):
        await hdhomerun_client.fetch_discover(TUNER_SETTINGS)


@respx.mock
async def test_fetch_discover_raises_hdhomerun_error_on_non_json_response():
    # e.g. tuner_port pointed at the streaming port instead of the JSON API
    # port — should degrade like any other reachability failure, not crash
    # with an unhandled ValueError.
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, content=b"\x00\x01\x02not json")
    )

    with pytest.raises(hdhomerun_client.HDHomeRunError):
        await hdhomerun_client.fetch_discover(TUNER_SETTINGS)


@respx.mock
async def test_fetch_discover_normalizes_host_with_scheme_and_trailing_slash():
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))

    result = await hdhomerun_client.fetch_discover({**TUNER_SETTINGS, "tuner_host": "http://hdhr.local/"})

    assert result["FriendlyName"] == "HDHomeRun FLEX 4K"


@respx.mock
async def test_fetch_lineup_maps_channels():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))

    channels = await hdhomerun_client.fetch_lineup(TUNER_SETTINGS)

    assert channels[0] == {
        "channel_number": "4.1",
        "name": "WCMH-DT",
        "is_hd": True,
        "is_drm": False,
        "stream_url": "http://hdhr.local:5004/auto/v4.1",
    }
    assert channels[1]["is_drm"] is True
    assert channels[1]["is_hd"] is False


@respx.mock
async def test_fetch_tuner_status_maps_defensively_when_fields_missing():
    respx.get("http://hdhr.local:80/status.json").mock(return_value=httpx.Response(200, json=[{}]))

    statuses = await hdhomerun_client.fetch_tuner_status(TUNER_SETTINGS)

    assert statuses == [
        {
            "index": 0,
            "in_use": False,
            "channel_number": None,
            "channel_name": None,
            "signal_strength_percent": None,
            "signal_quality_percent": None,
            "symbol_quality_percent": None,
            "network_rate_bps": None,
        }
    ]


@respx.mock
async def test_fetch_tuner_status_returns_empty_list_on_error():
    respx.get("http://hdhr.local:80/status.json").mock(return_value=httpx.Response(500))

    statuses = await hdhomerun_client.fetch_tuner_status(TUNER_SETTINGS)

    assert statuses == []


@respx.mock
async def test_fetch_guide_returns_none_when_no_device_auth():
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun"})
    )

    guide = await hdhomerun_client.fetch_guide(TUNER_SETTINGS, "w1")

    assert guide is None


@respx.mock
async def test_fetch_guide_returns_none_on_cloud_failure():
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(403))

    guide = await hdhomerun_client.fetch_guide(TUNER_SETTINGS, "w2")

    assert guide is None


@respx.mock
async def test_fetch_guide_parses_now_and_next():
    now = time.time()
    guide_response = [
        {
            "GuideNumber": "4.1",
            "Guide": [
                {"StartTime": now - 100, "EndTime": now + 100, "Title": "Local News", "EpisodeTitle": "Evening"},
                {"StartTime": now + 100, "EndTime": now + 200, "Title": "Next Show", "EpisodeTitle": None},
            ],
        }
    ]
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(200, json=guide_response))

    guide = await hdhomerun_client.fetch_guide(TUNER_SETTINGS, "w3")

    assert guide[0]["channel_number"] == "4.1"
    assert guide[0]["now"]["title"] == "Local News"
    assert guide[0]["next"]["title"] == "Next Show"


@respx.mock
async def test_fetch_guide_caches_discover_response():
    cache.delete("hdhomerun_discover:w4")
    discover_route = respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json=DISCOVER_RESPONSE)
    )
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(200, json=[]))

    await hdhomerun_client.fetch_guide(TUNER_SETTINGS, "w4")
    await hdhomerun_client.fetch_guide(TUNER_SETTINGS, "w4")

    assert discover_route.call_count == 1


@respx.mock
async def test_fetch_full_guide_paginates_across_multiple_days():
    cache.delete("hdhomerun_full_guide:w7")
    now = int(time.time())
    page1 = [
        {
            "GuideNumber": "4.1",
            "GuideName": "WCMH-DT",
            "Guide": [{"StartTime": now, "EndTime": now + 8 * 3600, "Title": "Show A"}],
        }
    ]
    page2 = [
        {
            "GuideNumber": "4.1",
            "GuideName": "WCMH-DT",
            "Guide": [{"StartTime": now + 24 * 3600, "EndTime": now + 25 * 3600, "Title": "Show B"}],
        }
    ]
    page3: list = []
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    guide_route = respx.get("https://api.hdhomerun.com/api/guide.php")
    guide_route.side_effect = [
        httpx.Response(200, json=page1),
        httpx.Response(200, json=page2),
        httpx.Response(200, json=page3),
    ]

    guide = await hdhomerun_client.fetch_full_guide(TUNER_SETTINGS, "w7")

    assert guide_route.call_count == 3
    assert len(guide) == 1
    titles = [a["title"] for a in guide[0]["airings"]]
    assert titles == ["Show A", "Show B"]
    first_params = guide_route.calls[0].request.url.params
    assert first_params["Start"] == str(now)
    assert first_params["Duration"] == "24"
    second_params = guide_route.calls[1].request.url.params
    assert second_params["Start"] == str(now + 24 * 3600)


@respx.mock
async def test_fetch_full_guide_stops_when_page_has_no_entries():
    cache.delete("hdhomerun_full_guide:w8")
    now = int(time.time())
    page1 = [
        {
            "GuideNumber": "4.1",
            "GuideName": "WCMH-DT",
            "Guide": [{"StartTime": now, "EndTime": now + 8 * 3600, "Title": "Show A"}],
        }
    ]
    # A channel entry with an empty Guide list — reached the free/subscribed
    # data ceiling but the response still lists the channel.
    page2 = [{"GuideNumber": "4.1", "GuideName": "WCMH-DT", "Guide": []}]
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    guide_route = respx.get("https://api.hdhomerun.com/api/guide.php")
    guide_route.side_effect = [httpx.Response(200, json=page1), httpx.Response(200, json=page2)]

    guide = await hdhomerun_client.fetch_full_guide(TUNER_SETTINGS, "w8")

    assert guide_route.call_count == 2
    assert len(guide[0]["airings"]) == 1


@respx.mock
async def test_fetch_full_guide_caches_result():
    cache.delete("hdhomerun_full_guide:w9")
    guide_route = respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))

    await hdhomerun_client.fetch_full_guide(TUNER_SETTINGS, "w9")
    await hdhomerun_client.fetch_full_guide(TUNER_SETTINGS, "w9")

    assert guide_route.call_count == 1


@respx.mock
async def test_fetch_full_guide_returns_none_on_total_failure():
    cache.delete("hdhomerun_full_guide:w10")
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))
    respx.get("https://api.hdhomerun.com/api/guide.php").mock(return_value=httpx.Response(403))

    guide = await hdhomerun_client.fetch_full_guide(TUNER_SETTINGS, "w10")

    assert guide is None


@respx.mock
async def test_build_lineup_with_guide_degrades_when_guide_unavailable():
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun"})
    )

    channels, guide_available = await hdhomerun_client.build_lineup_with_guide(TUNER_SETTINGS, "w5")

    assert guide_available is False
    assert len(channels) == 2
    assert channels[0]["now"] is None
    assert channels[0]["next"] is None


def _xmltv_time(epoch_seconds: float) -> str:
    return time.strftime("%Y%m%d%H%M%S +0000", time.gmtime(epoch_seconds))


def _xmltv_doc(channel_id: str, programmes: list[tuple[float, float, str, str | None]]) -> bytes:
    entries = "".join(
        f'<programme channel="{channel_id}" start="{_xmltv_time(start)}" stop="{_xmltv_time(end)}">'
        f"<title>{title}</title>" + (f"<sub-title>{sub_title}</sub-title>" if sub_title else "") + "</programme>"
        for start, end, title, sub_title in programmes
    )
    return f'<?xml version="1.0"?><tv>{entries}</tv>'.encode()


async def test_fetch_xmltv_guide_returns_none_when_epg_url_unset():
    guide = await hdhomerun_client.fetch_xmltv_guide(TUNER_SETTINGS, "x1")

    assert guide is None


@respx.mock
async def test_fetch_xmltv_guide_parses_now_and_next():
    now = time.time()
    respx.get("http://epg.example/guide.xml").mock(
        return_value=httpx.Response(
            200,
            content=_xmltv_doc(
                "4.1",
                [
                    (now - 100, now + 100, "Local News", "Evening"),
                    (now + 100, now + 200, "Next Show", None),
                ],
            ),
        )
    )
    settings = {**TUNER_SETTINGS, "epg_url": "http://epg.example/guide.xml"}

    guide = await hdhomerun_client.fetch_xmltv_guide(settings, "x2")

    assert guide == [
        {
            "channel_number": "4.1",
            "now": {"title": "Local News", "episode_title": "Evening"},
            "next": {"title": "Next Show", "episode_title": None},
        }
    ]


@respx.mock
async def test_fetch_xmltv_guide_returns_none_on_http_error():
    respx.get("http://epg.example/guide.xml").mock(return_value=httpx.Response(500))
    settings = {**TUNER_SETTINGS, "epg_url": "http://epg.example/guide.xml"}

    guide = await hdhomerun_client.fetch_xmltv_guide(settings, "x3")

    assert guide is None


@respx.mock
async def test_fetch_xmltv_guide_returns_none_on_malformed_xml():
    respx.get("http://epg.example/guide.xml").mock(return_value=httpx.Response(200, content=b"not xml <<<"))
    settings = {**TUNER_SETTINGS, "epg_url": "http://epg.example/guide.xml"}

    guide = await hdhomerun_client.fetch_xmltv_guide(settings, "x4")

    assert guide is None


@respx.mock
async def test_fetch_xmltv_guide_caches_parsed_result():
    now = time.time()
    route = respx.get("http://epg.example/guide.xml").mock(
        return_value=httpx.Response(200, content=_xmltv_doc("4.1", [(now - 10, now + 10, "Local News", None)]))
    )
    settings = {**TUNER_SETTINGS, "epg_url": "http://epg.example/guide.xml"}

    await hdhomerun_client.fetch_xmltv_guide(settings, "x5")
    await hdhomerun_client.fetch_xmltv_guide(settings, "x5")

    assert route.call_count == 1


@respx.mock
async def test_build_lineup_with_guide_falls_back_to_xmltv_when_cloud_guide_unavailable():
    now = time.time()
    respx.get("http://hdhr.local:80/lineup.json").mock(return_value=httpx.Response(200, json=LINEUP_RESPONSE))
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun"})
    )
    respx.get("http://epg.example/guide.xml").mock(
        return_value=httpx.Response(200, content=_xmltv_doc("4.1", [(now - 10, now + 10, "Local News", None)]))
    )
    settings = {**TUNER_SETTINGS, "epg_url": "http://epg.example/guide.xml"}

    channels, guide_available = await hdhomerun_client.build_lineup_with_guide(settings, "x6")

    assert guide_available is True
    assert channels[0]["now"] == {"title": "Local News", "episode_title": None}


@respx.mock
async def test_build_lineup_with_guide_merges_by_channel_number():
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

    channels, guide_available = await hdhomerun_client.build_lineup_with_guide(TUNER_SETTINGS, "w6")

    assert guide_available is True
    assert channels[0]["now"]["title"] == "Local News"
    assert channels[1]["now"] is None


@respx.mock
async def test_test_tuner_connection_returns_friendly_name():
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(200, json=DISCOVER_RESPONSE))

    name = await hdhomerun_client.test_tuner_connection(TUNER_SETTINGS)

    assert name == "HDHomeRun FLEX 4K"


@respx.mock
async def test_test_tuner_connection_raises_on_error():
    respx.get("http://hdhr.local:80/discover.json").mock(return_value=httpx.Response(500))

    with pytest.raises(hdhomerun_client.HDHomeRunError):
        await hdhomerun_client.test_tuner_connection(TUNER_SETTINGS)


@respx.mock
async def test_test_dvr_connection_returns_friendly_name():
    respx.get("http://dvr.local:59090/discover.json").mock(
        return_value=httpx.Response(200, json={"FriendlyName": "HDHomeRun RECORD"})
    )

    name = await hdhomerun_client.test_dvr_connection(DVR_SETTINGS)

    assert name == "HDHomeRun RECORD"


@respx.mock
async def test_test_dvr_connection_raises_on_error():
    respx.get("http://dvr.local:59090/discover.json").mock(return_value=httpx.Response(500))

    with pytest.raises(hdhomerun_client.HDHomeRunError):
        await hdhomerun_client.test_dvr_connection(DVR_SETTINGS)


@respx.mock
async def test_fetch_dvr_recordings_degrades_to_empty_list_on_error():
    respx.get("http://dvr.local:59090/discover.json").mock(return_value=httpx.Response(500))

    recordings = await hdhomerun_client.fetch_dvr_recordings(DVR_SETTINGS)

    assert recordings == []


@respx.mock
async def test_fetch_dvr_recordings_maps_fields():
    respx.get("http://dvr.local:59090/discover.json").mock(
        return_value=httpx.Response(
            200, json={"FriendlyName": "HDHomeRun RECORD", "StorageURL": "http://dvr.local:59090/recorded_files.json"}
        )
    )
    respx.get("http://dvr.local:59090/recorded_files.json").mock(
        return_value=httpx.Response(200, json=[{"Title": "Local News", "ChannelAffiliate": "NBC"}])
    )

    recordings = await hdhomerun_client.fetch_dvr_recordings(DVR_SETTINGS)

    assert recordings[0]["title"] == "Local News"
    assert recordings[0]["channel_name"] == "NBC"


@respx.mock
async def test_fetch_dvr_recording_rules_degrades_to_empty_list_on_error():
    respx.get("http://dvr.local:59090/recording_rules.json").mock(return_value=httpx.Response(500))

    rules = await hdhomerun_client.fetch_dvr_recording_rules(DVR_SETTINGS)

    assert rules == []
