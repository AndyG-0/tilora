from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.integrations import jellyfin_client
from app.storage.cache import cache

API_KEY_SETTINGS = {"host": "jf.local", "port": 8096, "use_https": False, "auth_mode": "api_key", "api_key": "k1"}
PASSWORD_SETTINGS = {
    "host": "jf.local",
    "port": 8096,
    "use_https": False,
    "auth_mode": "password",
    "username": "user",
    "password": "pass",
}


def test_is_configured_true_for_api_key():
    assert jellyfin_client.is_configured(API_KEY_SETTINGS)


def test_is_configured_true_for_password():
    assert jellyfin_client.is_configured(PASSWORD_SETTINGS)


def test_is_configured_false_when_no_host():
    assert not jellyfin_client.is_configured({"auth_mode": "api_key", "api_key": "k1"})


def test_is_configured_false_when_password_mode_missing_password():
    assert not jellyfin_client.is_configured({"host": "jf.local", "auth_mode": "password", "username": "u"})


def test_item_dict_maps_fields():
    result = jellyfin_client._item_dict(
        {
            "Id": "abc",
            "Name": "Movie Night",
            "Type": "Movie",
            "Overview": "A movie.",
            "ProductionYear": 2020,
            "IsFolder": False,
            "ImageTags": {"Primary": "tag123"},
            "RunTimeTicks": 60_000_000_000,
        }
    )
    assert result == {
        "id": "abc",
        "name": "Movie Night",
        "type": "Movie",
        "overview": "A movie.",
        "year": 2020,
        "is_folder": False,
        "has_poster": True,
        "runtime_minutes": 100,
    }


def test_item_dict_defaults_when_fields_missing():
    result = jellyfin_client._item_dict({"Id": "abc"})
    assert result["name"] == ""
    assert result["has_poster"] is False
    assert result["runtime_minutes"] is None


async def test_resolve_connection_api_key_mode_makes_no_request():
    conn = await jellyfin_client.resolve_connection(API_KEY_SETTINGS, "w1")
    assert conn.base_url == "http://jf.local:8096"
    assert conn.headers == {"X-Emby-Token": "k1"}
    assert conn.user_id is None


async def test_resolve_connection_missing_api_key_raises():
    with pytest.raises(jellyfin_client.JellyfinError):
        await jellyfin_client.resolve_connection({"host": "jf.local", "auth_mode": "api_key"}, "w1")


@respx.mock
async def test_resolve_connection_password_mode_authenticates_and_caches():
    route = respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(
        return_value=httpx.Response(200, json={"AccessToken": "tok1", "User": {"Id": "u1"}})
    )

    conn = await jellyfin_client.resolve_connection(PASSWORD_SETTINGS, "w2")

    assert route.called
    assert conn.headers == {"X-Emby-Token": "tok1"}
    assert conn.user_id == "u1"
    assert cache.get("jellyfin_token:w2") == {"access_token": "tok1", "user_id": "u1"}


@respx.mock
async def test_resolve_connection_password_mode_reuses_cached_token():
    route = respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(
        return_value=httpx.Response(200, json={"AccessToken": "tok1", "User": {"Id": "u1"}})
    )

    await jellyfin_client.resolve_connection(PASSWORD_SETTINGS, "w3")
    await jellyfin_client.resolve_connection(PASSWORD_SETTINGS, "w3")

    assert route.call_count == 1


@respx.mock
async def test_resolve_connection_password_mode_rejects_bad_credentials():
    respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(return_value=httpx.Response(401))

    with pytest.raises(jellyfin_client.JellyfinError):
        await jellyfin_client.resolve_connection(PASSWORD_SETTINGS, "w4")


@respx.mock
async def test_test_connection_returns_server_name():
    respx.get("http://jf.local:8096/System/Info").mock(
        return_value=httpx.Response(200, json={"ServerName": "Home Server"})
    )

    name = await jellyfin_client.test_connection(API_KEY_SETTINGS, "w5")

    assert name == "Home Server"


@respx.mock
async def test_test_connection_raises_on_error_status():
    respx.get("http://jf.local:8096/System/Info").mock(return_value=httpx.Response(500))

    with pytest.raises(jellyfin_client.JellyfinError):
        await jellyfin_client.test_connection(API_KEY_SETTINGS, "w6")


@respx.mock
async def test_request_retries_once_on_401_in_password_mode():
    auth_route = respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(
        side_effect=[
            httpx.Response(200, json={"AccessToken": "stale", "User": {"Id": "u1"}}),
            httpx.Response(200, json={"AccessToken": "fresh", "User": {"Id": "u1"}}),
        ]
    )
    info_route = respx.get("http://jf.local:8096/System/Info").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"ServerName": "Home Server"})]
    )

    name = await jellyfin_client.test_connection(PASSWORD_SETTINGS, "w7")

    assert name == "Home Server"
    assert auth_route.call_count == 2
    assert info_route.call_count == 2


@respx.mock
async def test_list_children_uses_media_folders_for_api_key_mode():
    route = respx.get("http://jf.local:8096/Library/MediaFolders").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "lib1", "Name": "Movies", "IsFolder": True}]})
    )

    items = await jellyfin_client.list_children(API_KEY_SETTINGS, "w8", parent_id=None)

    assert route.called
    assert items == [
        {
            "id": "lib1",
            "name": "Movies",
            "type": "",
            "overview": None,
            "year": None,
            "is_folder": True,
            "has_poster": False,
            "runtime_minutes": None,
        }
    ]


@respx.mock
async def test_list_children_uses_items_endpoint_for_parent():
    route = respx.get("http://jf.local:8096/Items", params={"ParentId": "lib1"}).mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "m1", "Name": "A Movie", "IsFolder": False}]})
    )

    items = await jellyfin_client.list_children(API_KEY_SETTINGS, "w9", parent_id="lib1")

    assert route.called
    assert items[0]["id"] == "m1"


async def test_list_resume_items_returns_empty_for_api_key_auth():
    items = await jellyfin_client.list_resume_items(API_KEY_SETTINGS, "w16")

    assert items == []


@respx.mock
async def test_list_resume_items_uses_the_authenticated_users_resume_endpoint():
    respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(
        return_value=httpx.Response(200, json={"AccessToken": "tok1", "User": {"Id": "u1"}})
    )
    route = respx.get("http://jf.local:8096/Users/u1/Items/Resume").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "m1", "Name": "Half-watched", "IsFolder": False}]})
    )

    items = await jellyfin_client.list_resume_items(PASSWORD_SETTINGS, "w17")

    assert route.called
    assert items[0]["id"] == "m1"


@respx.mock
async def test_fetch_image_bytes_returns_none_on_error():
    respx.get("http://jf.local:8096/Items/missing/Images/Primary").mock(return_value=httpx.Response(404))

    result = await jellyfin_client.fetch_image_bytes(API_KEY_SETTINGS, "w10", "missing")

    assert result is None


@respx.mock
async def test_fetch_image_bytes_returns_content_and_type():
    respx.get("http://jf.local:8096/Items/pic1/Images/Primary").mock(
        return_value=httpx.Response(200, content=b"bytes", headers={"content-type": "image/jpeg"})
    )

    result = await jellyfin_client.fetch_image_bytes(API_KEY_SETTINGS, "w11", "pic1")

    assert result == (b"bytes", "image/jpeg")


@respx.mock
async def test_fetch_image_bytes_requests_a_capped_thumbnail_size():
    route = respx.get("http://jf.local:8096/Items/pic1/Images/Primary", params={"maxWidth": "400"}).mock(
        return_value=httpx.Response(200, content=b"bytes", headers={"content-type": "image/jpeg"})
    )

    await jellyfin_client.fetch_image_bytes(API_KEY_SETTINGS, "w12", "pic1")

    assert route.called


@respx.mock
async def test_open_video_stream_requests_static_passthrough():
    route = respx.get("http://jf.local:8096/Videos/vid1/stream").mock(return_value=httpx.Response(200, content=b"data"))

    client, response = await jellyfin_client.open_video_stream(API_KEY_SETTINGS, "w13", "vid1", None)
    await response.aclose()
    await client.aclose()

    assert route.called
    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params == {"static": "true"}


@respx.mock
async def test_open_video_stream_forwards_range_header():
    route = respx.get("http://jf.local:8096/Videos/vid1/stream").mock(return_value=httpx.Response(206, content=b"data"))

    client, response = await jellyfin_client.open_video_stream(API_KEY_SETTINGS, "w14", "vid1", "bytes=100-")
    await response.aclose()
    await client.aclose()

    assert route.called
    assert route.calls.last.request.headers.get("range") == "bytes=100-"


@respx.mock
async def test_open_hls_playlist_requests_master_with_expected_params():
    route = respx.get("http://jf.local:8096/Videos/vid1/master.m3u8").mock(
        return_value=httpx.Response(200, text="#EXTM3U\n")
    )

    text = await jellyfin_client.open_hls_playlist(API_KEY_SETTINGS, "w15", "vid1", play_session_id="sess1")

    assert route.called
    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params["VideoCodec"] == "h264,hevc"
    assert params["AudioCodec"] == "aac"
    assert params["DeviceId"] == "dashboard-w15"
    assert params["PlaySessionId"] == "sess1"
    # Jellyfin 400s ("The mediaSourceId field is required") without this.
    assert params["MediaSourceId"] == "vid1"
    assert text == "#EXTM3U\n"


@respx.mock
async def test_open_hls_playlist_forwards_audio_stream_index():
    route = respx.get("http://jf.local:8096/Videos/vid1/master.m3u8").mock(
        return_value=httpx.Response(200, text="#EXTM3U\n")
    )

    await jellyfin_client.open_hls_playlist(
        API_KEY_SETTINGS, "w16", "vid1", audio_stream_index=3, play_session_id="sess1"
    )

    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params["AudioStreamIndex"] == "3"


@respx.mock
async def test_open_hls_playlist_raises_on_error_status():
    respx.get("http://jf.local:8096/Videos/vid1/master.m3u8").mock(return_value=httpx.Response(500))

    with pytest.raises(jellyfin_client.JellyfinError):
        await jellyfin_client.open_hls_playlist(API_KEY_SETTINGS, "w17", "vid1", play_session_id="sess1")


def test_rewrite_hls_playlist_rewrites_media_playlist_segment_uris():
    text = "#EXTM3U\n#EXTINF:6.0,\n0.ts?a=1\n#EXTINF:6.0,\nsegs/1.ts\n#EXT-X-ENDLIST\n"

    rewritten = jellyfin_client.rewrite_hls_playlist(text, "w1", "vid1", "/Videos/vid1/main.m3u8")

    lines = rewritten.splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[2] == "/api/jellyfin/w1/hls-resource/vid1?path=%2FVideos%2Fvid1%2F0.ts%3Fa%3D1"
    assert lines[4] == "/api/jellyfin/w1/hls-resource/vid1?path=%2FVideos%2Fvid1%2Fsegs%2F1.ts"
    assert lines[5] == "#EXT-X-ENDLIST"


def test_rewrite_hls_playlist_rewrites_nested_variant_playlist_uri():
    text = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nmain/master.m3u8\n"

    rewritten = jellyfin_client.rewrite_hls_playlist(text, "w1", "vid1", "/Videos/vid1/master.m3u8")

    assert "hls-resource/vid1?path=%2FVideos%2Fvid1%2Fmain%2Fmaster.m3u8" in rewritten.splitlines()[2]


def test_rewrite_hls_playlist_resolves_relative_uris_against_the_nested_playlists_own_path():
    text = "#EXTM3U\n0.ts\n"

    rewritten = jellyfin_client.rewrite_hls_playlist(text, "w1", "vid1", "/Videos/vid1/main/master.m3u8")

    assert "path=%2FVideos%2Fvid1%2Fmain%2F0.ts" in rewritten.splitlines()[1]


@respx.mock
async def test_open_hls_resource_streams_bytes_with_auth_header():
    route = respx.get("http://jf.local:8096/Videos/vid1/0.ts", params={"a": "1"}).mock(
        return_value=httpx.Response(200, content=b"segment-bytes")
    )

    client, response = await jellyfin_client.open_hls_resource(API_KEY_SETTINGS, "w18", "/Videos/vid1/0.ts", "a=1")
    content = await response.aread()
    await response.aclose()
    await client.aclose()

    assert route.called
    assert route.calls.last.request.headers.get("x-emby-token") == "k1"
    assert content == b"segment-bytes"


@respx.mock
async def test_stop_playback_session_posts_session_id_and_position():
    route = respx.post("http://jf.local:8096/Sessions/Playing/Stopped").mock(return_value=httpx.Response(204))

    await jellyfin_client.stop_playback_session(API_KEY_SETTINGS, "w19", "vid1", "sess1", 12.5)

    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "ItemId": "vid1",
        "MediaSourceId": "vid1",
        "PlaySessionId": "sess1",
        "PositionTicks": 125_000_000,
    }


@respx.mock
async def test_stop_playback_session_swallows_errors():
    respx.post("http://jf.local:8096/Sessions/Playing/Stopped").mock(return_value=httpx.Response(500))

    # Best-effort cleanup — a failure here must never raise into the caller.
    await jellyfin_client.stop_playback_session(API_KEY_SETTINGS, "w20", "vid1", "sess1", 0)


@respx.mock
async def test_report_playback_start_posts_session_info():
    route = respx.post("http://jf.local:8096/Sessions/Playing").mock(return_value=httpx.Response(204))

    await jellyfin_client.report_playback_start(API_KEY_SETTINGS, "w21", "vid1", "sess1")

    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "ItemId": "vid1",
        "MediaSourceId": "vid1",
        "PlaySessionId": "sess1",
        "PlayMethod": "Transcode",
        "CanSeek": True,
    }


@respx.mock
async def test_report_playback_start_swallows_errors():
    respx.post("http://jf.local:8096/Sessions/Playing").mock(return_value=httpx.Response(500))

    await jellyfin_client.report_playback_start(API_KEY_SETTINGS, "w22", "vid1", "sess1")


@respx.mock
async def test_report_playback_progress_posts_position_ticks():
    route = respx.post("http://jf.local:8096/Sessions/Playing/Progress").mock(return_value=httpx.Response(204))

    await jellyfin_client.report_playback_progress(API_KEY_SETTINGS, "w23", "vid1", "sess1", 90.25, is_paused=True)

    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "ItemId": "vid1",
        "MediaSourceId": "vid1",
        "PlaySessionId": "sess1",
        "PlayMethod": "Transcode",
        "PositionTicks": 902_500_000,
        "IsPaused": True,
    }


@respx.mock
async def test_report_playback_progress_swallows_errors():
    respx.post("http://jf.local:8096/Sessions/Playing/Progress").mock(return_value=httpx.Response(500))

    await jellyfin_client.report_playback_progress(API_KEY_SETTINGS, "w24", "vid1", "sess1", 10)


@respx.mock
async def test_get_item_detail_parses_streams_and_chapters():
    item_payload = {
        "Id": "m100",
        "Name": "Sample Movie",
        "Type": "Movie",
        "Overview": "Overview text",
        "ProductionYear": 2024,
        "RunTimeTicks": 72000000000,
        "Container": "mkv",
        "MediaStreams": [
            {
                "Type": "Video",
                "Index": 0,
                "Codec": "h264",
                "Width": 1920,
                "Height": 1080,
                "AspectRatio": "16:9",
                "RealFrameRate": 24.0,
                "BitRate": 5000000,
            },
            {
                "Type": "Audio",
                "Index": 1,
                "Title": "English 5.1",
                "DisplayTitle": "English (AAC 5.1)",
                "Language": "eng",
                "Codec": "aac",
                "Channels": 6,
                "IsDefault": True,
            },
            {
                "Type": "Subtitle",
                "Index": 2,
                "DisplayTitle": "English SDH",
                "Language": "eng",
                "Codec": "subrip",
                "IsDefault": True,
                "IsForced": False,
            },
        ],
        "Chapters": [
            {"Name": "Chapter 1", "StartPositionTicks": 0},
            {"Name": "Chapter 2", "StartPositionTicks": 3000000000},
        ],
    }
    route = respx.get("http://jf.local:8096/Items/m100").mock(return_value=httpx.Response(200, json=item_payload))

    detail = await jellyfin_client.get_item_detail(API_KEY_SETTINGS, "w18", "m100")

    assert route.called
    assert detail["name"] == "Sample Movie"
    assert detail["year"] == 2024
    assert detail["runtime_minutes"] == 120
    assert len(detail["audio_streams"]) == 1
    assert detail["audio_streams"][0]["display_title"] == "English (AAC 5.1)"
    assert len(detail["subtitle_streams"]) == 1
    assert detail["subtitle_streams"][0]["index"] == 2
    assert len(detail["chapters"]) == 2
    assert detail["chapters"][1]["start_seconds"] == 300.0


@respx.mock
async def test_fetch_subtitle_vtt_returns_content():
    route = respx.get("http://jf.local:8096/Videos/vid1/Subtitles/2/0/Stream.vtt").mock(
        return_value=httpx.Response(200, content=b"WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello")
    )

    content = await jellyfin_client.fetch_subtitle_vtt(API_KEY_SETTINGS, "w19", "vid1", 2)

    assert route.called
    assert content.startswith(b"WEBVTT")
