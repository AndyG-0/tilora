from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import immich_client

BASE_URL = "http://192.168.1.50:2283/api"
SEARCH_URL = f"{BASE_URL}/search/metadata"
API_KEY = "test-api-key"
ALBUM_ID = "b1f5c3d0-1234-4abc-89ab-0123456789ab"


def _asset(
    asset_id: str,
    filename: str = "IMG_0001.jpg",
    asset_type: str = "IMAGE",
    is_trashed: bool = False,
    width: int | None = 4032,
    height: int | None = 3024,
) -> dict:
    # Trimmed but structurally faithful copy of a real Immich v3.1.0
    # AssetResponseDto (per the published OpenAPI spec) — only the fields
    # this client actually reads are populated meaningfully, the rest are
    # present so this looks like a real payload.
    return {
        "id": asset_id,
        "originalFileName": filename,
        "type": asset_type,
        "isTrashed": is_trashed,
        "isArchived": False,
        "isFavorite": False,
        "width": width,
        "height": height,
        "checksum": "abc123",
        "ownerId": "owner-1",
        "originalPath": "/data/upload/owner-1/original.jpg",
    }


def _search_response(items: list[dict], next_page: str | None = None) -> dict:
    return {
        "albums": {"count": 0, "items": [], "total": 0},
        "assets": {"count": len(items), "items": items, "nextPage": next_page, "total": len(items)},
    }


def test_is_configured_requires_all_three_fields():
    assert immich_client.is_configured({"base_url": BASE_URL, "api_key": API_KEY, "album_id": ALBUM_ID})
    assert not immich_client.is_configured({"base_url": BASE_URL, "api_key": API_KEY})
    assert not immich_client.is_configured({"base_url": BASE_URL, "album_id": ALBUM_ID})
    assert not immich_client.is_configured({"api_key": API_KEY, "album_id": ALBUM_ID})
    assert not immich_client.is_configured({})


def test_normalize_base_url_strips_trailing_slash():
    assert immich_client.normalize_base_url("http://host:2283/api/") == "http://host:2283/api"
    assert immich_client.normalize_base_url("http://host:2283/api") == "http://host:2283/api"
    assert immich_client.normalize_base_url("http://host:2283/api///") == "http://host:2283/api"


# --- iter_album_asset_chunks -------------------------------------------------


@respx.mock
async def test_iter_album_asset_chunks_yields_images_and_skips_video_and_trashed():
    items = [
        _asset("asset-1", "a.jpg"),
        _asset("asset-2", "video.mp4", asset_type="VIDEO"),
        _asset("asset-3", "trashed.jpg", is_trashed=True),
        _asset("asset-4", "b.jpg"),
    ]
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response(items)))

    chunks = [chunk async for chunk in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID)]

    assert chunks == [
        [
            {"id": "asset-1", "filename": "a.jpg", "width": 4032, "height": 3024},
            {"id": "asset-4", "filename": "b.jpg", "width": 4032, "height": 3024},
        ]
    ]


@respx.mock
async def test_iter_album_asset_chunks_sends_api_key_header_and_album_filter():
    route = respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))

    async for _ in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID):
        pass

    assert route.called
    request = route.calls[0].request
    assert request.headers["x-api-key"] == API_KEY
    import json

    body = json.loads(request.content)
    assert body["albumIds"] == [ALBUM_ID]
    assert body["page"] == 1


@respx.mock
async def test_iter_album_asset_chunks_paginates_via_next_page():
    page1 = _search_response([_asset("asset-1")], next_page="2")
    page2 = _search_response([_asset("asset-2")], next_page=None)
    respx.post(SEARCH_URL).mock(side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json=page2)])

    chunks = [chunk async for chunk in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID)]

    assert chunks == [
        [{"id": "asset-1", "filename": "IMG_0001.jpg", "width": 4032, "height": 3024}],
        [{"id": "asset-2", "filename": "IMG_0001.jpg", "width": 4032, "height": 3024}],
    ]


@respx.mock
async def test_iter_album_asset_chunks_empty_album_yields_nothing():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))

    chunks = [chunk async for chunk in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID)]

    assert chunks == []


async def test_iter_album_asset_chunks_yields_nothing_when_not_configured():
    assert [c async for c in immich_client.iter_album_asset_chunks("", API_KEY, ALBUM_ID)] == []
    assert [c async for c in immich_client.iter_album_asset_chunks(BASE_URL, "", ALBUM_ID)] == []
    assert [c async for c in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, "")] == []


@respx.mock
async def test_iter_album_asset_chunks_avoids_infinite_loop_on_cyclic_next_page():
    # A malformed/buggy server that keeps echoing back the same nextPage
    # token must not hang the background indexer forever.
    looping = _search_response([_asset("asset-1")], next_page="1")
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=looping))

    chunks = [chunk async for chunk in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID)]

    assert chunks == [[{"id": "asset-1", "filename": "IMG_0001.jpg", "width": 4032, "height": 3024}]]


@respx.mock
async def test_iter_album_asset_chunks_degrades_to_nothing_on_unexpected_shape():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={"oops": True}))

    chunks = [chunk async for chunk in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID)]

    assert chunks == []


@respx.mock
async def test_iter_album_asset_chunks_raises_on_server_error_status():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(500))

    with pytest.raises(immich_client.ImmichError):
        async for _ in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID):
            pass


@respx.mock
async def test_iter_album_asset_chunks_raises_actionable_message_on_401():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(401, json={"message": "Unauthorized", "statusCode": 401}))

    with pytest.raises(immich_client.ImmichError, match="API key"):
        async for _ in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID):
            pass


@respx.mock
async def test_iter_album_asset_chunks_raises_with_server_message_on_400():
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(400, json={"message": "albumIds must be a UUID", "statusCode": 400})
    )

    with pytest.raises(immich_client.ImmichError, match="albumIds must be a UUID"):
        async for _ in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID):
            pass


@respx.mock
async def test_iter_album_asset_chunks_raises_on_non_json_response():
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(immich_client.ImmichError):
        async for _ in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID):
            pass


@respx.mock
async def test_iter_album_asset_chunks_raises_on_connect_error():
    respx.post(SEARCH_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(immich_client.ImmichError):
        async for _ in immich_client.iter_album_asset_chunks(BASE_URL, API_KEY, ALBUM_ID):
            pass


# --- fetch_asset_bytes -------------------------------------------------------


@respx.mock
async def test_fetch_asset_bytes_returns_content_and_type():
    url = f"{BASE_URL}/assets/asset-1/thumbnail"
    respx.get(url).mock(return_value=httpx.Response(200, content=b"jpeg-bytes", headers={"content-type": "image/jpeg"}))

    result = await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "asset-1")

    assert result == (b"jpeg-bytes", "image/jpeg")


@respx.mock
async def test_fetch_asset_bytes_sends_api_key_header_and_size_param():
    url = f"{BASE_URL}/assets/asset-1/thumbnail"
    route = respx.get(url).mock(return_value=httpx.Response(200, content=b"bytes"))

    await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "asset-1")

    request = route.calls[0].request
    assert request.headers["x-api-key"] == API_KEY
    assert request.url.params["size"] == "preview"


@respx.mock
async def test_fetch_asset_bytes_defaults_content_type_when_header_missing():
    url = f"{BASE_URL}/assets/asset-1/thumbnail"
    respx.get(url).mock(return_value=httpx.Response(200, content=b"bytes"))

    result = await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "asset-1")

    assert result is not None
    assert result[1] == "image/jpeg"


@respx.mock
async def test_fetch_asset_bytes_returns_none_on_404():
    url = f"{BASE_URL}/assets/missing/thumbnail"
    respx.get(url).mock(return_value=httpx.Response(404, json={"message": "Not found"}))

    result = await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "missing")

    assert result is None


@respx.mock
async def test_fetch_asset_bytes_raises_on_server_error():
    url = f"{BASE_URL}/assets/asset-1/thumbnail"
    respx.get(url).mock(return_value=httpx.Response(500))

    with pytest.raises(immich_client.ImmichError):
        await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "asset-1")


@respx.mock
async def test_fetch_asset_bytes_raises_actionable_message_on_403():
    url = f"{BASE_URL}/assets/asset-1/thumbnail"
    respx.get(url).mock(return_value=httpx.Response(403, json={"message": "Forbidden"}))

    with pytest.raises(immich_client.ImmichError, match="API key"):
        await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "asset-1")


@respx.mock
async def test_fetch_asset_bytes_raises_on_connect_error():
    url = f"{BASE_URL}/assets/asset-1/thumbnail"
    respx.get(url).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(immich_client.ImmichError):
        await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "asset-1")


async def test_fetch_asset_bytes_returns_none_for_missing_params():
    assert await immich_client.fetch_asset_bytes("", API_KEY, "asset-1") is None
    assert await immich_client.fetch_asset_bytes(BASE_URL, "", "asset-1") is None
    assert await immich_client.fetch_asset_bytes(BASE_URL, API_KEY, "") is None
