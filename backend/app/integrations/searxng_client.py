"""SearXNG search client and web page text fetcher.

Provides external web search and URL content extraction for the AI assistant
when an admin configures a SearXNG instance URL in settings.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_SEARCH_LIMIT = 5
_DEFAULT_MAX_FETCH_CHARS = 4000
_USER_AGENT = "Tilora/1.0 (Smart Dashboard AI Assistant)"
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class SearXNGError(Exception):
    """Raised when SearXNG cannot be reached or returns an error."""


class _HTMLTextExtractor(HTMLParser):
    """Extracts readable text content from HTML while ignoring scripts/styles."""

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._ignore_depth = 0
        self._ignored_tags = {"script", "style", "noscript", "svg", "head", "iframe", "nav", "footer"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self._ignored_tags:
            self._ignore_depth += 1
        elif tag_lower in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "article", "section"}:
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self._ignored_tags:
            self._ignore_depth = max(0, self._ignore_depth - 1)
        elif tag_lower in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "article", "section"}:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def extract_text_from_html(html_content: str) -> str:
    """Strip HTML tags and boilerplate to produce readable plain text."""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html_content)
        parser.close()
        return parser.get_text()
    except Exception as exc:
        logger.debug("HTML parsing fallback due to error: %s", exc)
        # Fallback simple regex tag strip if parser hits unexpected malformed tokens
        text = re.sub(r"<[^>]+>", " ", html_content)
        return re.sub(r"\s+", " ", text).strip()


async def search(query: str, searxng_url: str, limit: int = _DEFAULT_SEARCH_LIMIT) -> list[dict[str, Any]]:
    """Query SearXNG JSON API for web search results.

    Returns a list of `{"title": ..., "url": ..., "snippet": ...}`.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    base_url = searxng_url.strip().rstrip("/")
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        raise SearXNGError("Invalid SearXNG URL scheme. Must start with http:// or https://")
    search_url = f"{base_url}/search"

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(
                search_url,
                params={"q": clean_query, "format": "json"},
                headers={"User-Agent": _USER_AGENT},
            )
        except httpx.HTTPError as exc:
            logger.warning("Failed to reach SearXNG at %s: %s", search_url, exc)
            raise SearXNGError(f"Could not reach SearXNG: {exc}") from exc

    if response.status_code >= 400:
        raise SearXNGError(f"SearXNG returned HTTP {response.status_code}: {response.text[:200]}")

    try:
        data = response.json()
    except ValueError as exc:
        raise SearXNGError(f"SearXNG returned invalid JSON: {exc}") from exc

    results: list[dict[str, Any]] = []
    raw_results = data.get("results") if isinstance(data, dict) else []
    if isinstance(raw_results, list):
        for item in raw_results[:limit]:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or ""
            url = item.get("url") or ""
            snippet = item.get("content") or item.get("snippet") or ""
            if url:
                results.append({"title": title, "url": url, "snippet": snippet})

    return results


async def fetch_page(url: str, max_chars: int = _DEFAULT_MAX_FETCH_CHARS) -> dict[str, Any]:
    """Fetch and extract readable plain text content from a web page URL."""
    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return {"url": clean_url, "error": "Invalid URL scheme. Must start with http:// or https://"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_SECONDS, follow_redirects=True) as client:
        try:
            response = await client.get(clean_url, headers={"User-Agent": _BROWSER_USER_AGENT})
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch page %s: %s", clean_url, exc)
            return {"url": clean_url, "error": f"Failed to reach web page: {exc}"}

    if response.status_code >= 400:
        return {"url": clean_url, "error": f"Web page returned HTTP {response.status_code}"}

    content_type = response.headers.get("content-type", "").lower()
    text_content = response.text

    if "text/html" in content_type or "<html" in text_content.lower()[:500]:
        text = extract_text_from_html(text_content)
    else:
        text = text_content.strip()

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated to {max_chars} characters]"

    return {"url": clean_url, "content": text}
