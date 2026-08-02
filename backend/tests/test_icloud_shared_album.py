from __future__ import annotations

import httpx
import respx

from app.integrations import icloud_shared_album

TOKEN = "B0z5qAGN1JIFd3y"
DEFAULT_HOST = icloud_shared_album._DEFAULT_HOST


def _webstream_json(guid="guid-1", checksum="chk-1", width=1600, height=1200):
    return {
        "photos": [
            {
                "photoGuid": guid,
                "derivatives": {
                    "1200": {"checksum": "chk-small", "width": 400, "height": 300},
                    "1600": {"checksum": checksum, "width": width, "height": height},
                },
            }
        ]
    }


def test_parse_token_from_full_share_url():
    url = "https://www.icloud.com/sharedalbum/#B0z5qAGN1JIFd3y"

    assert icloud_shared_album.parse_token(url) == "B0z5qAGN1JIFd3y"


def test_parse_token_passes_through_bare_token():
    assert icloud_shared_album.parse_token("B0z5qAGN1JIFd3y") == "B0z5qAGN1JIFd3y"


def test_is_configured():
    assert icloud_shared_album.is_configured("token") is True
    assert icloud_shared_album.is_configured(None) is False
    assert icloud_shared_album.is_configured("") is False


@respx.mock
async def test_fetch_photos_returns_largest_derivative():
    respx.post(f"https://{DEFAULT_HOST}/{TOKEN}/sharedstreams/webstream").mock(
        return_value=httpx.Response(200, json=_webstream_json())
    )

    photos = await icloud_shared_album.fetch_photos(TOKEN)

    assert photos == [{"guid": "guid-1", "checksum": "chk-1", "width": 1600, "height": 1200}]


@respx.mock
async def test_fetch_photos_follows_partition_host_redirect():
    other_host = "p99-sharedstreams.icloud.com"
    respx.post(f"https://{DEFAULT_HOST}/{TOKEN}/sharedstreams/webstream").mock(
        return_value=httpx.Response(200, headers={"X-Apple-MMe-Host": other_host}, json={"photos": []})
    )
    respx.post(f"https://{other_host}/{TOKEN}/sharedstreams/webstream").mock(
        return_value=httpx.Response(200, json=_webstream_json())
    )

    photos = await icloud_shared_album.fetch_photos(TOKEN)

    assert photos == [{"guid": "guid-1", "checksum": "chk-1", "width": 1600, "height": 1200}]


@respx.mock
async def test_fetch_photos_is_cached_across_calls():
    route = respx.post(f"https://{DEFAULT_HOST}/{TOKEN}/sharedstreams/webstream").mock(
        return_value=httpx.Response(200, json=_webstream_json())
    )

    await icloud_shared_album.fetch_photos(TOKEN)
    await icloud_shared_album.fetch_photos(TOKEN)

    assert route.call_count == 1


@respx.mock
async def test_fetch_asset_url_builds_url_from_location_and_path():
    respx.post(f"https://{DEFAULT_HOST}/{TOKEN}/sharedstreams/webasseturls").mock(
        return_value=httpx.Response(
            200,
            json={"items": {"chk-1": {"url_location": "cvws.icloud-content.com", "url_path": "/B/abc?o=1"}}},
        )
    )

    url = await icloud_shared_album.fetch_asset_url(TOKEN, "guid-1", "chk-1")

    assert url == "https://cvws.icloud-content.com/B/abc?o=1"


@respx.mock
async def test_fetch_asset_url_is_cached_across_calls():
    route = respx.post(f"https://{DEFAULT_HOST}/{TOKEN}/sharedstreams/webasseturls").mock(
        return_value=httpx.Response(
            200,
            json={"items": {"chk-1": {"url_location": "cvws.icloud-content.com", "url_path": "/B/abc"}}},
        )
    )

    await icloud_shared_album.fetch_asset_url(TOKEN, "guid-1", "chk-1")
    await icloud_shared_album.fetch_asset_url(TOKEN, "guid-1", "chk-1")

    assert route.call_count == 1


@respx.mock
async def test_fetch_asset_url_returns_none_when_checksum_missing():
    respx.post(f"https://{DEFAULT_HOST}/{TOKEN}/sharedstreams/webasseturls").mock(
        return_value=httpx.Response(200, json={"items": {}})
    )

    url = await icloud_shared_album.fetch_asset_url(TOKEN, "guid-1", "chk-missing")

    assert url is None
