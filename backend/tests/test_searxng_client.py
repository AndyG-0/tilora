from __future__ import annotations

import httpx
import pytest

from app.integrations import searxng_client


def test_extract_text_from_html():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <script>var x = 123;</script>
        <style>body { color: red; }</style>
    </head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <h1>Main Headline</h1>
        <p>This is the first paragraph with <a href="#">a link</a>.</p>
        <p>Second paragraph text.</p>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """
    text = searxng_client.extract_text_from_html(html)
    assert "var x = 123" not in text
    assert "body { color: red; }" not in text
    assert "Main Headline" in text
    assert "This is the first paragraph with a link." in text
    assert "Second paragraph text." in text


async def test_search_empty_query():
    results = await searxng_client.search("", "http://searxng.test")
    assert results == []


async def test_search_success(monkeypatch):
    searxng_response = {
        "query": "dallas cowboys",
        "results": [
            {
                "title": "Dallas Cowboys News",
                "url": "https://example.com/cowboys",
                "content": "Latest Dallas Cowboys scores and schedule.",
            },
            {
                "title": "NFL Standings",
                "url": "https://example.com/nfl",
                "content": "Full NFL standings and upcoming games.",
            },
        ],
    }

    async def fake_get(self, url, params=None, headers=None):
        assert "http://searxng.test/search" in url
        assert params["q"] == "dallas cowboys"
        assert params["format"] == "json"
        return httpx.Response(200, json=searxng_response, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    results = await searxng_client.search("dallas cowboys", "http://searxng.test/")
    assert len(results) == 2
    assert results[0]["title"] == "Dallas Cowboys News"
    assert results[0]["url"] == "https://example.com/cowboys"
    assert results[0]["snippet"] == "Latest Dallas Cowboys scores and schedule."


async def test_search_http_error(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        return httpx.Response(500, text="Internal Error", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(searxng_client.SearXNGError, match="HTTP 500"):
        await searxng_client.search("test", "http://searxng.test")


async def test_fetch_page_invalid_url():
    res = await searxng_client.fetch_page("ftp://invalid.com")
    assert "error" in res
    assert "Invalid URL scheme" in res["error"]


async def test_fetch_page_success_html(monkeypatch):
    html_content = "<html><body><h1>Article</h1><p>Important news content.</p></body></html>"

    async def fake_get(self, url, headers=None):
        return httpx.Response(
            200,
            text=html_content,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    res = await searxng_client.fetch_page("https://example.com/news")
    assert res["url"] == "https://example.com/news"
    assert "Article" in res["content"]
    assert "Important news content." in res["content"]


async def test_fetch_page_truncation(monkeypatch):
    long_text = "word " * 1000

    async def fake_get(self, url, headers=None):
        return httpx.Response(
            200,
            text=long_text,
            headers={"content-type": "text/plain"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    res = await searxng_client.fetch_page("https://example.com/long", max_chars=100)
    assert len(res["content"]) < 200
    assert "... [truncated to 100 characters]" in res["content"]
