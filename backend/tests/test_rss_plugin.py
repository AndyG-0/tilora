from __future__ import annotations

import httpx
import respx

from app.plugins.rss.plugin import RSSPlugin
from app.storage import db

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
<media:thumbnail xmlns:media="http://search.yahoo.com/mrss/" url="https://example.com/newer.jpg"/>
</item>
</channel>
</rss>
"""


def make_plugin(widget_id: str = "rss", user_id: str | None = "user-1", **settings) -> RSSPlugin:
    return RSSPlugin({"id": widget_id, "settings": settings, "user_id": user_id})


@respx.mock
async def test_get_summary_groups_items_by_feed(tmp_db):
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    respx.get("https://example.com/two.xml").mock(return_value=httpx.Response(200, content=FEED_TWO))
    one = db.add_rss_feed("user-1", "https://example.com/one.xml", None)
    two = db.add_rss_feed("user-1", "https://example.com/two.xml", "Custom")
    plugin = make_plugin(feed_ids=[one["id"], two["id"]])

    summary = await plugin.get_summary()

    assert summary["title"] == "Headlines"
    groups = {group["name"]: group for group in summary["feed_groups"]}
    assert groups.keys() == {"Feed One", "Custom"}
    assert groups["Feed One"]["items"][0]["title"] == "Older Item"
    assert groups["Custom"]["items"][0]["title"] == "Newer Item"
    assert "summary" not in groups["Feed One"]["items"][0]
    assert "image" not in groups["Custom"]["items"][0]


@respx.mock
async def test_get_summary_respects_each_feeds_own_item_limit(tmp_db):
    respx.get("https://example.com/one.xml").mock(
        return_value=httpx.Response(200, content=_feed_with_n_items("One", 5))
    )
    feed = db.add_rss_feed("user-1", "https://example.com/one.xml", None, item_limit=2)
    plugin = make_plugin(feed_ids=[feed["id"]])

    summary = await plugin.get_summary()

    assert len(summary["feed_groups"][0]["items"]) == 2


def _feed_with_n_items(title: str, n: int) -> bytes:
    items = "".join(
        f"<item><title>{title} Item {i}</title><link>https://example.com/{title}/{i}</link>"
        f"<pubDate>{(1 + i):02d} Jan 2026 12:00:00 GMT</pubDate></item>"
        for i in range(n)
    )
    return f"<?xml version='1.0'?><rss version='2.0'><channel><title>{title}</title>{items}</channel></rss>".encode()


@respx.mock
async def test_get_detail_strips_html_from_summary(tmp_db):
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    feed = db.add_rss_feed("user-1", "https://example.com/one.xml", None)
    plugin = make_plugin(feed_ids=[feed["id"]])

    detail = await plugin.get_detail()

    assert detail["feed_groups"][0]["items"][0]["summary"] == "Older description"


@respx.mock
async def test_get_detail_extracts_media_thumbnail_image(tmp_db):
    respx.get("https://example.com/two.xml").mock(return_value=httpx.Response(200, content=FEED_TWO))
    feed = db.add_rss_feed("user-1", "https://example.com/two.xml", None)
    plugin = make_plugin(feed_ids=[feed["id"]])

    detail = await plugin.get_detail()

    assert detail["feed_groups"][0]["items"][0]["image"] == "https://example.com/newer.jpg"


@respx.mock
async def test_get_detail_includes_full_feed_catalog_and_selection(tmp_db):
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    one = db.add_rss_feed("user-1", "https://example.com/one.xml", None)
    two = db.add_rss_feed("user-1", "https://example.com/two.xml", "Custom")
    plugin = make_plugin(title="Tech News", feed_ids=[one["id"]])

    detail = await plugin.get_detail()

    assert detail["title"] == "Tech News"
    assert detail["feed_ids"] == [one["id"]]
    assert {feed["id"] for feed in detail["all_feeds"]} == {one["id"], two["id"]}


@respx.mock
async def test_get_detail_degrades_a_failing_feed_to_an_error_without_dropping_others(tmp_db):
    respx.get("https://example.com/broken.xml").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/two.xml").mock(return_value=httpx.Response(200, content=FEED_TWO))
    broken = db.add_rss_feed("user-1", "https://example.com/broken.xml", "Broken")
    two = db.add_rss_feed("user-1", "https://example.com/two.xml", "Custom")
    plugin = make_plugin(feed_ids=[broken["id"], two["id"]])

    detail = await plugin.get_detail()

    groups = {group["name"]: group for group in detail["feed_groups"]}
    assert groups["Broken"]["items"] == []
    assert groups["Broken"]["error"]
    assert groups["Custom"]["items"][0]["title"] == "Newer Item"
    assert "error" not in groups["Custom"]


@respx.mock
async def test_get_summary_degrades_a_failing_feed_to_an_error_without_dropping_others(tmp_db):
    respx.get("https://example.com/broken.xml").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/two.xml").mock(return_value=httpx.Response(200, content=FEED_TWO))
    broken = db.add_rss_feed("user-1", "https://example.com/broken.xml", "Broken")
    two = db.add_rss_feed("user-1", "https://example.com/two.xml", "Custom")
    plugin = make_plugin(feed_ids=[broken["id"], two["id"]])

    summary = await plugin.get_summary()

    groups = {group["name"]: group for group in summary["feed_groups"]}
    assert groups["Broken"]["items"] == []
    assert groups["Broken"]["error"]
    assert groups["Custom"]["items"][0]["title"] == "Newer Item"
    assert "error" not in groups["Custom"]


@respx.mock
async def test_get_detail_degrades_a_feed_that_times_out(tmp_db):
    respx.get("https://example.com/slow.xml").mock(side_effect=httpx.ConnectTimeout("timed out"))
    feed = db.add_rss_feed("user-1", "https://example.com/slow.xml", "Slow")
    plugin = make_plugin(feed_ids=[feed["id"]])

    detail = await plugin.get_detail()

    assert detail["feed_groups"][0]["items"] == []
    assert detail["feed_groups"][0]["error"]


@respx.mock
async def test_get_detail_degrades_a_feed_that_is_not_valid_xml(tmp_db):
    respx.get("https://example.com/junk.xml").mock(return_value=httpx.Response(200, content=b"not xml at all"))
    feed = db.add_rss_feed("user-1", "https://example.com/junk.xml", "Junk")
    plugin = make_plugin(feed_ids=[feed["id"]])

    detail = await plugin.get_detail()

    assert detail["feed_groups"][0]["items"] == []
    assert detail["feed_groups"][0]["error"]


async def test_get_summary_without_a_requesting_user_returns_no_groups(tmp_db):
    feed = db.add_rss_feed("user-1", "https://example.com/one.xml", None)
    plugin = make_plugin(user_id=None, feed_ids=[feed["id"]])

    summary = await plugin.get_summary()

    assert summary == {"title": "Headlines", "feed_groups": []}


async def test_get_summary_title_defaults_to_headlines(tmp_db):
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["title"] == "Headlines"
    assert summary["feed_groups"] == []


def test_default_settings_start_with_no_selected_feeds():
    assert RSSPlugin.default_settings == {"title": "Headlines", "feed_ids": []}


@respx.mock
async def test_get_ai_tools_exposes_latest_headlines_tool(tmp_db):
    respx.get("https://example.com/one.xml").mock(return_value=httpx.Response(200, content=FEED_ONE))
    feed = db.add_rss_feed("user-1", "https://example.com/one.xml", None)
    plugin = make_plugin(feed_ids=[feed["id"]])

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_latest_headlines_rss"
    result = await tools[0].handler()
    assert result["feed_groups"][0]["items"][0]["title"] == "Older Item"


def test_get_ai_tools_names_are_scoped_per_widget_instance():
    first = make_plugin(widget_id="rss-aaa1111", title="Tech News")
    second = make_plugin(widget_id="rss-bbb2222", title="Sports")

    first_tool = first.get_ai_tools()[0]
    second_tool = second.get_ai_tools()[0]

    assert first_tool.name != second_tool.name
    assert first_tool.name == "get_latest_headlines_rss-aaa1111"
    assert "Tech News" in first_tool.description
    assert "Sports" in second_tool.description
