from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import nasa_client

IMAGE_RESPONSE = {
    "title": "A Beautiful Nebula",
    "explanation": "Some nebula.",
    "url": "https://apod.nasa.gov/apod/image/nebula.jpg",
    "hdurl": "https://apod.nasa.gov/apod/image/nebula_hd.jpg",
    "media_type": "image",
    "date": "2026-08-05",
    "copyright": "Jane Astronomer",
}

VIDEO_RESPONSE = {
    "title": "A Cool Video",
    "explanation": "Some video.",
    "url": "https://www.youtube.com/embed/abc123",
    "media_type": "video",
    "date": "2026-08-06",
    "thumbnail_url": "https://img.youtube.com/vi/abc123/0.jpg",
}


@respx.mock
async def test_get_apod_parses_an_image_day():
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))

    result = await nasa_client.get_apod("test-key")

    assert result == {
        "title": "A Beautiful Nebula",
        "explanation": "Some nebula.",
        "url": "https://apod.nasa.gov/apod/image/nebula.jpg",
        "hdurl": "https://apod.nasa.gov/apod/image/nebula_hd.jpg",
        "thumbnail_url": None,
        "media_type": "image",
        "date": "2026-08-05",
        "copyright": "Jane Astronomer",
    }


@respx.mock
async def test_get_apod_parses_a_video_day_with_thumbnail():
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=VIDEO_RESPONSE))

    result = await nasa_client.get_apod("test-key")

    assert result["media_type"] == "video"
    assert result["thumbnail_url"] == "https://img.youtube.com/vi/abc123/0.jpg"
    assert result["hdurl"] is None


@respx.mock
async def test_get_apod_sends_the_configured_api_key():
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))

    await nasa_client.get_apod("my-key")

    assert route.calls.last.request.url.params["api_key"] == "my-key"


@respx.mock
async def test_get_apod_falls_back_to_demo_key_when_unset():
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))

    await nasa_client.get_apod(None)

    assert route.calls.last.request.url.params["api_key"] == "DEMO_KEY"


@respx.mock
async def test_get_apod_sends_a_date_when_given():
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))

    await nasa_client.get_apod("test-key", date="2026-08-05")

    assert route.calls.last.request.url.params["date"] == "2026-08-05"


@respx.mock
async def test_get_apod_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    respx.get("https://api.nasa.gov/planetary/apod").mock(
        return_value=httpx.Response(429, json={"error": {"message": "rate limit exceeded"}})
    )

    with pytest.raises(nasa_client.NASAError, match="rate limit exceeded"):
        await nasa_client.get_apod("test-key")


@respx.mock
async def test_get_apod_raises_on_network_error(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    respx.get("https://api.nasa.gov/planetary/apod").mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(nasa_client.NASAError):
        await nasa_client.get_apod("test-key")


@respx.mock
async def test_get_apod_retries_once_on_a_connection_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=IMAGE_RESPONSE)]
    )

    result = await nasa_client.get_apod("test-key")

    assert result["title"] == "A Beautiful Nebula"
    assert route.call_count == 2


@respx.mock
async def test_get_apod_retries_once_on_a_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(
        side_effect=[
            httpx.Response(429, json={"error": {"message": "rate limit exceeded"}}),
            httpx.Response(200, json=IMAGE_RESPONSE),
        ]
    )

    result = await nasa_client.get_apod("test-key")

    assert result["title"] == "A Beautiful Nebula"
    assert route.call_count == 2


@respx.mock
async def test_get_apod_retries_once_on_a_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=IMAGE_RESPONSE)]
    )

    result = await nasa_client.get_apod("test-key")

    assert result["title"] == "A Beautiful Nebula"
    assert route.call_count == 2


@respx.mock
async def test_get_apod_does_not_retry_on_a_non_retryable_4xx(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(
        return_value=httpx.Response(400, json={"msg": "bad date"})
    )

    with pytest.raises(nasa_client.NASAError, match="bad date"):
        await nasa_client.get_apod("test-key")

    assert route.call_count == 1


@respx.mock
async def test_get_apod_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    route = respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(503))

    with pytest.raises(nasa_client.NASAError):
        await nasa_client.get_apod("test-key")

    assert route.call_count == nasa_client._MAX_ATTEMPTS
