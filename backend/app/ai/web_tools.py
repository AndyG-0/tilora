"""Web search and URL content fetching tools for the AI assistant.

Tools are active only when an admin configures a SearXNG instance URL in settings.
"""

from __future__ import annotations

from typing import Any

from app.integrations import searxng_client
from app.plugins.base import ToolDef


def get_web_tools(searxng_url: str | None) -> list[ToolDef]:
    """Return web search and fetch tools if a SearXNG URL is configured, else []."""
    if not searxng_url or not searxng_url.strip():
        return []

    target_searxng_url = searxng_url.strip()

    async def web_search(query: str, limit: int = 5) -> dict[str, Any]:
        try:
            results = await searxng_client.search(query, target_searxng_url, limit=limit)
            return {"query": query, "results": results}
        except searxng_client.SearXNGError as exc:
            return {"query": query, "error": str(exc)}

    async def web_fetch(url: str) -> dict[str, Any]:
        return await searxng_client.fetch_page(url)

    return [
        ToolDef(
            name="web_search",
            description=(
                "Search the web using SearXNG. Returns titles, URLs, and text snippets for top search results. "
                "Use this when you need live, real-time, or external internet information not available in "
                "local dashboard tools."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web.",
                    },
                },
                "required": ["query"],
            },
            handler=web_search,
        ),
        ToolDef(
            name="web_fetch",
            description=(
                "Fetch and extract readable plain text content from a web page URL. "
                "Use this to read full articles, details, or documentation from a URL returned by web_search."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The HTTP or HTTPS URL of the web page to fetch.",
                    },
                },
                "required": ["url"],
            },
            handler=web_fetch,
        ),
    ]
