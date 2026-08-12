from __future__ import annotations

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
async def test_open_video_stream_compatible_mode_transcodes_audio_only():
    route = respx.get("http://jf.local:8096/Videos/vid1/stream").mock(return_value=httpx.Response(200, content=b"data"))

    client, response = await jellyfin_client.open_video_stream(API_KEY_SETTINGS, "w13", "vid1", None)
    await response.aclose()
    await client.aclose()

    assert route.called
    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params["static"] == "false"
    assert params["VideoCodec"] == "copy"
    assert params["AudioCodec"] == "aac"


@respx.mock
async def test_open_video_stream_compatible_video_mode_transcodes_video_too():
    settings = {**API_KEY_SETTINGS, "playback_mode": "compatible_video"}
    route = respx.get("http://jf.local:8096/Videos/vid1/stream").mock(return_value=httpx.Response(200, content=b"data"))

    client, response = await jellyfin_client.open_video_stream(settings, "w15", "vid1", None)
    await response.aclose()
    await client.aclose()

    assert route.called
    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params["static"] == "false"
    assert params["VideoCodec"] == "h264"
    assert params["AudioCodec"] == "aac"


@respx.mock
async def test_open_video_stream_direct_mode_requests_static_passthrough():
    settings = {**API_KEY_SETTINGS, "playback_mode": "direct"}
    route = respx.get("http://jf.local:8096/Videos/vid1/stream").mock(return_value=httpx.Response(200, content=b"data"))

    client, response = await jellyfin_client.open_video_stream(settings, "w14", "vid1", None)
    await response.aclose()
    await client.aclose()

    assert route.called
    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params == {"static": "true"}


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


@respx.mock
async def test_open_video_stream_with_audio_stream_index():
    route = respx.get("http://jf.local:8096/Videos/vid1/stream").mock(return_value=httpx.Response(200, content=b"data"))

    client, response = await jellyfin_client.open_video_stream(API_KEY_SETTINGS, "w20", "vid1", None, audio_stream_index=2)
    await response.aclose()
    await client.aclose()

    assert route.called
    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))
    assert params["AudioStreamIndex"] == "2"

