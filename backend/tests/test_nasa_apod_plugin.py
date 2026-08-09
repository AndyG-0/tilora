from __future__ import annotations

import httpx
import respx

from app.config import settings
from app.integrations import nasa_client
from app.plugins.nasa_apod.plugin import NASAApodPlugin
from app.storage import db

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


def make_plugin(widget_id: str = "nasa_apod", **settings) -> NASAApodPlugin:
    return NASAApodPlugin({"id": widget_id, "settings": settings})


@respx.mock
async def test_get_summary_returns_the_image_url_for_an_image_day(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["available"] is True
    assert summary["apod_title"] == "A Beautiful Nebula"
    assert summary["media_type"] == "image"
    assert summary["thumbnail_url"] == "https://apod.nasa.gov/apod/image/nebula.jpg"
    assert summary["stale"] is False


@respx.mock
async def test_get_summary_returns_the_thumbnail_url_for_a_video_day(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=VIDEO_RESPONSE))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["media_type"] == "video"
    assert summary["thumbnail_url"] == "https://img.youtube.com/vi/abc123/0.jpg"


@respx.mock
async def test_get_summary_uses_the_custom_title(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))
    plugin = make_plugin(title="Space Pic")

    summary = await plugin.get_summary()

    assert summary["title"] == "Space Pic"


@respx.mock
async def test_get_summary_degrades_gracefully_on_api_error(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {"title": "NASA Astronomy Picture of the Day", "available": False}


@respx.mock
async def test_get_summary_persists_on_successful_fetch(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))
    plugin = make_plugin()

    await plugin.get_summary()

    persisted = db.latest_nasa_apod_fetch(plugin.id)
    assert persisted is not None
    assert persisted["title"] == "A Beautiful Nebula"


@respx.mock
async def test_get_summary_falls_back_to_last_good_fetch_on_failure(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    db.record_nasa_apod_fetch("nasa_apod", IMAGE_RESPONSE)
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["available"] is True
    assert summary["stale"] is True
    assert summary["apod_title"] == "A Beautiful Nebula"
    assert "fetched_at" in summary


@respx.mock
async def test_get_detail_includes_the_full_explanation_and_copyright(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(200, json=IMAGE_RESPONSE))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["available"] is True
    assert detail["title"] == "NASA Astronomy Picture of the Day"
    assert detail["apod_title"] == "A Beautiful Nebula"
    assert detail["explanation"] == "Some nebula."
    assert detail["hdurl"] == "https://apod.nasa.gov/apod/image/nebula_hd.jpg"
    assert detail["copyright"] == "Jane Astronomer"
    assert detail["stale"] is False


@respx.mock
async def test_get_detail_degrades_gracefully_on_api_error(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail == {"title": "NASA Astronomy Picture of the Day", "available": False}


@respx.mock
async def test_get_detail_falls_back_to_last_good_fetch_on_failure(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")
    monkeypatch.setattr(nasa_client, "_RETRY_BACKOFF_SECONDS", 0)
    db.record_nasa_apod_fetch("nasa_apod", IMAGE_RESPONSE)
    respx.get("https://api.nasa.gov/planetary/apod").mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["available"] is True
    assert detail["stale"] is True
    assert detail["explanation"] == "Some nebula."
    assert detail["hdurl"] == "https://apod.nasa.gov/apod/image/nebula_hd.jpg"
    assert "fetched_at" in detail
