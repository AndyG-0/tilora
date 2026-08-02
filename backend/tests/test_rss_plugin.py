from __future__ import annotations

import httpx
import respx

from app.plugins.rss.plugin import RSSPlugin

FEED_ONE = b"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>Feed One</title>
<item>
<title>Older Item</title>
<link>https://example.com/older</link>
<description>Older &lt;b&gt;description&lt;/b&gt;</description>
<pubDate>Mon, 01 Jan 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""

FEED_TWO = b"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>Feed Two</title>
<item>
<title>Newer Item</title>
<link>https://example.com/newer</link>
<description>Newer description</description>
<pubDate>Wed, 03 Jan 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""


def make_plugin(widget_id: str = "rss", **settings) -> RSSPlugin:
    return RSSPlugin({"id": widget_id, "settings": settings})


@respx.mock
async def test_get_summary_merges_and_sorts_feeds_by_published_date():
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    respx.get("https://example.com/two.xml").mock(return_value=httpx.Response(200, content=FEED_TWO))
    plugin = make_plugin(
        feeds=[{"url": "https://example.com/one.xml"}, {"url": "https://example.com/two.xml", "name": "Custom"}]
    )

    summary = await plugin.get_summary()

    assert [item["title"] for item in summary["items"]] == ["Newer Item", "Older Item"]
    assert summary["items"][0]["source"] == "Custom"
    assert summary["items"][1]["source"] == "Feed One"
    assert "summary" not in summary["items"][0]


@respx.mock
async def test_get_summary_respects_item_limit():
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    respx.get("https://example.com/two.xml").mock(return_value=httpx.Response(200, content=FEED_TWO))
    plugin = make_plugin(
        feeds=[{"url": "https://example.com/one.xml"}, {"url": "https://example.com/two.xml"}],
        item_limit=1,
    )

    summary = await plugin.get_summary()

    assert len(summary["items"]) == 1


@respx.mock
async def test_get_detail_strips_html_from_summary():
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    plugin = make_plugin(feeds=[{"url": "https://example.com/one.xml"}])

    detail = await plugin.get_detail()

    assert detail["items"][0]["summary"] == "Older description"


@respx.mock
async def test_get_detail_includes_current_feed_settings():
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    feeds = [{"url": "https://example.com/one.xml", "name": "Custom"}]
    plugin = make_plugin(title="Tech News", feeds=feeds, item_limit=3)

    detail = await plugin.get_detail()

    assert detail["title"] == "Tech News"
    assert detail["feeds"] == feeds
    assert detail["item_limit"] == 3


async def test_get_summary_title_defaults_to_headlines():
    plugin = make_plugin(feeds=[])

    summary = await plugin.get_summary()

    assert summary["title"] == "Headlines"


def test_default_settings_start_with_an_empty_feed_list():
    assert RSSPlugin.default_settings == {"title": "Headlines", "feeds": [], "item_limit": 5}


@respx.mock
async def test_get_ai_tools_exposes_latest_headlines_tool():
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    plugin = make_plugin(feeds=[{"url": "https://example.com/one.xml"}])

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_latest_headlines_rss"
    result = await tools[0].handler()
    assert result["items"][0]["title"] == "Older Item"


def test_get_ai_tools_names_are_scoped_per_widget_instance():
    first = make_plugin(widget_id="rss-aaa1111", title="Tech News", feeds=[])
    second = make_plugin(widget_id="rss-bbb2222", title="Sports", feeds=[])

    first_tool = first.get_ai_tools()[0]
    second_tool = second.get_ai_tools()[0]

    assert first_tool.name != second_tool.name
    assert first_tool.name == "get_latest_headlines_rss-aaa1111"
    assert "Tech News" in first_tool.description
    assert "Sports" in second_tool.description
